from google.cloud import vision


def detect_text_gcs(bucket_name, file_name):
    """
    Detects text in an image file located in Google Cloud Storage.
    Cloud Shell and other Google Cloud environments provide automatic authentication.
    """
    # 1. 认证方式修改：
    # 在Cloud Shell中，客户端会自动使用环境的认证信息，无需指定密钥文件。
    # 旧代码：client = vision.ImageAnnotatorClient.from_service_account_file(key_path)
    client = vision.ImageAnnotatorClient()

    # 2. 图片读取方式修改：
    # 我们不再从本地读取文件内容，而是直接告诉API图片的GCS URI。
    image_uri = f"gs://{bucket_name}/{file_name}"

    print(f"开始识别位于 {image_uri} 的图片...")

    # 使用 vision.ImageSource 指定图片的云端位置
    image = vision.Image()
    image.source.image_uri = image_uri

    # 调用API进行识别（这部分逻辑不变）
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))

    print("完整的识别文本:")
    print(response.full_text_annotation.text)


# --- 主程序 ---
if __name__ == '__main__':
    # 3. 主程序变量修改：
    # 您需要在这里填入您的GCS存储桶名称和图片文件名。

    # (必填) 替换为您的 GCS 存储桶的名称
    bucket_name = "myocr-project-1"

    # (必填) 您上传到存储桶的图片文件名
    file_name = "1.png"

    # 检查用户是否已修改占位符
    if bucket_name == "your-bucket-name-here":
        print("错误：请在代码中修改 bucket_name 变量为您的实际存储桶名称。")
    else:
        detect_text_gcs(bucket_name, file_name)