export interface ProcessedImageResult {
  base64Data: string;
  mimeType: string;
  previewUrl: string;
}

/**
 * Compresses and resizes an uploaded image file so that base64 payloads remain fast and reliable.
 */
export function processUploadedImage(file: File, maxDimension = 1400): Promise<ProcessedImageResult> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          } else {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Không thể khởi tạo bộ xử lý ảnh.'));
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        const compressedUrl = canvas.toDataURL('image/jpeg', 0.85);
        const base64Data = compressedUrl.split(',')[1] || '';
        resolve({
          base64Data,
          mimeType: 'image/jpeg',
          previewUrl: compressedUrl,
        });
      };
      img.onerror = () => reject(new Error('Tệp hình ảnh không hợp lệ hoặc bị lỗi.'));
      img.src = dataUrl;
    };
    reader.onerror = () => reject(new Error('Không thể đọc tệp hình ảnh từ thiết bị.'));
    reader.readAsDataURL(file);
  });
}
