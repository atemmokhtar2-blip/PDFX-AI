
import fitz  # PyMuPDF
import os
import pandas as pd
import pdfplumber
from concurrent.futures import ThreadPoolExecutor
from image_recovery_engine import extract_and_process_image, recover_corrupted_image

def extract_page_data(page_num, doc, images_dir):
    """Helper to extract text and images from a single page."""
    page = doc[page_num]
    page_text = page.get_text("text")
    
    images = []
    for img_index, img in enumerate(page.get_images(full=True)):
        # Extract and process image using the new engine
        processed_image = extract_and_process_image(doc, page_num, img_index, img, images_dir)
        if processed_image:
            images.append(processed_image)
        else:
            # Attempt to recover corrupted images
            recovered_image = recover_corrupted_image(page, img[1], images_dir, page_num, img_index)
            if recovered_image:
                images.append(recovered_image)

    return page_num + 1, page_text, images

def extract_pdf_content(pdf_path: str, output_dir: str):
    doc = fitz.open(pdf_path)
    content = {
        "text": "",
        "pages": [],
        "images": [],
        "tables": [],
        "metadata": doc.metadata
    }

    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # Use ThreadPoolExecutor for faster text and image extraction
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda p: extract_page_data(p, doc, images_dir), range(len(doc))))

    # Sort results by page number and aggregate
    results.sort(key=lambda x: x[0])
    full_text = []
    for p_num, p_text, p_imgs in results:
        full_text.append(p_text)
        content["pages"].append({"page_num": p_num, "text": p_text})
        content["images"].extend(p_imgs)

    content["text"] = "\n\n".join(full_text)

    # Table extraction is usually slower, we limit it to the first 20 pages for speed if needed,
    # or keep it as is but optimize the process.
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Only process pages that actually have tables to save time
            for i, page in enumerate(pdf.pages):
                # Quick check if page might have a table before full extraction
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table and len(table) > 1: # Ignore empty or single-row "tables"
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
    # Limit text length to keep AI fast and within token limits
    # We take the most important parts if it's too long
    max_chars = 15000 
    
    prompt = f"Metadata: {content['metadata'].get('title', 'Unknown')}\n\n"
    
    current_len = 0
    for page in content["pages"]:
        page_content = f"[[ P{page['page_num']} ]]\n{page['text']}\n"
        if current_len + len(page_content) > max_chars:
            prompt += "... [Content truncated for brevity] ..."
            break
        prompt += page_content
        current_len += len(page_content)
    
    if content["tables"]:
        prompt += "\n--- TABLES ---\n"
        for table in content["tables"][:5]: # Limit to first 5 tables for speed
            prompt += f"T(P{table['page']}): {table['data']}\n"
            
    # Add image information to the prompt for the AI to use
    if content["images"]:
        prompt += "\n--- IMAGES ---\n"
        for img in content["images"]:
            # Include image as a smart box in the content_markdown for the AI to place
            # We'll use a simplified representation for the AI to interpret
            # The AI is expected to re-insert these into the content_markdown in logical places
            prompt += f":::image Image from Page {img["page"]}\n{img["path"]}\n{img.get("bbox", "")}\n:::\n"
            
    return prompt
