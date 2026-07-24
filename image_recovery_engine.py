
import fitz # PyMuPDF
import os
import cv2
import numpy as np

def enhance_image(image_bytes: bytes) -> bytes:
    """Enhances image quality, removes noise, and preserves dimensions."""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return image_bytes # Return original if decoding fails

        # Convert to grayscale for noise reduction (if color isn't critical)
        # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply noise reduction (e.g., Non-local Means Denoising)
        # This can be computationally intensive, consider a lighter filter if needed
        # For now, a simple median blur
        enhanced_img = cv2.medianBlur(img, 3) # Kernel size 3x3

        # Further enhancements like contrast adjustment could be added
        # For example: clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        # enhanced_img = clahe.apply(cv2.cvtColor(enhanced_img, cv2.COLOR_BGR2GRAY))
        # enhanced_img = cv2.cvtColor(enhanced_img, cv2.COLOR_GRAY2BGR)

        # Encode the enhanced image back to bytes
        _, buffer = cv2.imencode('.png', enhanced_img)
        return buffer.tobytes()
    except Exception as e:
        print(f"Error enhancing image: {e}")
        return image_bytes # Return original on error

def extract_and_process_image(doc, page_num: int, img_index: int, img_info, images_dir: str) -> dict or None:
    """Extracts, enhances, and saves a single image from a PDF page."""
    try:
        xref = img_info[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]

        # Enhance the image
        enhanced_image_bytes = enhance_image(image_bytes)

        image_filename = f"page{page_num+1}_img{img_index+1}.{image_ext}"
        image_path = os.path.join(images_dir, image_filename)

        with open(image_path, "wb") as f:
            f.write(enhanced_image_bytes)

        return {
            "path": image_path,
            "page": page_num + 1,
            "index": img_index + 1,
            "bbox": img_info[1] # Bounding box of the image on the page
        }
    except Exception as e:
        print(f"Could not extract or process image {img_index+1} on page {page_num+1}: {e}")
        return None

def recover_corrupted_image(page, bbox, images_dir, page_num, img_index) -> dict or None:
    """Attempts to recover a corrupted image by cropping it from the page or using OCR.
    This is a placeholder for more advanced recovery logic.
    """
    try:
        # Attempt to crop the image area from the page as a fallback
        rect = fitz.Rect(bbox)
        pix = page.get_pixmap(clip=rect)
        
        if pix.width == 0 or pix.height == 0:
            return None

        image_filename = f"page{page_num+1}_recovered_img{img_index+1}.png"
        image_path = os.path.join(images_dir, image_filename)
        pix.save(image_path)

        # TODO: Add OCR logic here if the cropped image contains text

        return {
            "path": image_path,
            "page": page_num + 1,
            "index": img_index + 1,
            "bbox": bbox,
            "recovered": True
        }
    except Exception as e:
        print(f"Error recovering image from page {page_num+1} at bbox {bbox}: {e}")
        return None

