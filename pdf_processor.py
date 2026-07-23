import fitz  # PyMuPDF
import os
import tempfile
import pandas as pd
import pdfplumber
from PIL import Image
import io

def extract_pdf_content(pdf_path: str, output_dir: str):
    """
    Extracts text, images, and tables from a PDF file.
    Returns a dictionary with the extracted content and structure.
    """
    doc = fitz.open(pdf_path)
    content = {
        "text": "",
        "pages": [],
        "images": [],
        "tables": [],
        "metadata": doc.metadata
    }

    # Create images directory
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # 1. Extract Text and Images using PyMuPDF
    full_text = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        full_text.append(page_text)
        
        content["pages"].append({
            "page_num": page_num + 1,
            "text": page_text
        })

        # Extract Images
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_filename = f"page{page_num+1}_img{img_index+1}.{image_ext}"
            image_path = os.path.join(images_dir, image_filename)
            
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            content["images"].append({
                "path": image_path,
                "page": page_num + 1,
                "index": img_index + 1
            })

    content["text"] = "\n\n".join(full_text)

    # 2. Extract Tables using pdfplumber (better for structure)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table:
                        # Clean table (remove None values)
                        df = pd.DataFrame(table)
                        content["tables"].append({
                            "page": i + 1,
                            "index": table_idx + 1,
                            "data": df.to_dict(orient="records")
                        })
    except Exception as e:
        print(f"Error extracting tables: {e}")

    doc.close()
    return content

def format_content_for_ai(content: dict) -> str:
    """
    Formats the extracted content into a prompt-friendly string for the AI.
    """
    prompt = f"Document Metadata: {content['metadata']}\n\n"
    prompt += "--- EXTRACTED CONTENT ---\n\n"
    
    for page in content["pages"]:
        prompt += f"[[ PAGE {page['page_num']} ]]\n"
        prompt += page["text"] + "\n\n"
    
    if content["tables"]:
        prompt += "--- TABLES FOUND ---\n"
        for table in content["tables"]:
            prompt += f"Table on Page {table['page']}:\n{table['data']}\n\n"
            
    return prompt
