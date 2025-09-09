# ocr_pdf_gcs.py
import re
from google.cloud import vision
from google.cloud import storage

def async_detect_document(gcs_source_uri, gcs_destination_uri):
    """
    发起一个异步的、针对GCS上PDF文件的OCR请求。
    此版本适用于Cloud Shell等已自动认证的环境。
    """
    print(f"开始对文件 {gcs_source_uri} 进行OCR识别...")

    # 1. 认证方式修改：
    # 客户端会自动使用Cloud Shell环境的认证信息，无需传入凭据。
    client = vision.ImageAnnotatorClient()
    storage_client = storage.Client()

    # --- PDF处理逻辑保持不变 ---
    gcs_source = vision.GcsSource(uri=gcs_source_uri)
    input_config = vision.InputConfig(
        gcs_source=gcs_source, mime_type='application/pdf')

    gcs_destination = vision.GcsDestination(uri=gcs_destination_uri)
    output_config = vision.OutputConfig(
        gcs_destination=gcs_destination, batch_size=5)

    feature = vision.Feature(
        type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)

    async_request = vision.AsyncAnnotateFileRequest(
        features=[feature], input_config=input_config,
        output_config=output_config)

    operation = client.async_batch_annotate_files(
        requests=[async_request])

    print('等待操作完成...')
    operation.result(timeout=420)  # 您可以根据PDF大小调整超时时间
    print('操作完成！结果已保存在GCS中。')

    # --- 解析结果的逻辑保持不变 ---
    match = re.match(r'gs://([^/]+)/(.+)', gcs_destination_uri)
    bucket_name = match.group(1)
    prefix = match.group(2)

    bucket = storage_client.get_bucket(bucket_name)

    blob_list = [blob for blob in list(bucket.list_blobs(prefix=prefix)) if not blob.name.endswith('/')]
    print(f'在 {gcs_destination_uri} 找到 {len(blob_list)} 个结果文件。')

    full_text = ""
    for blob in blob_list:
        json_string = blob.download_as_bytes().decode('utf-8')
        response = vision.AnnotateFileResponse.from_json(json_string)

        for page_response in response.responses:
            full_text += page_response.full_text_annotation.text
            full_text += '\n\n--- Page Break ---\n\n'

    return full_text


# --- 主程序 ---
if __name__ == '__main__':
    # 2. 主程序变量修改：
    # 现在您只需要修改下面2个变量即可

    # (必填) 您的GCS存储桶名称
    bucket_name = 'myocr-project-1'

    # (必填) 您上传到GCS的PDF文件名
    pdf_file_name = '高温合金旋压塑性成形理论与应用.pdf'

    # 检查用户是否已修改占位符
    if bucket_name == "your-bucket-name-here":
        print("错误：请在代码中修改 bucket_name 变量为您的实际存储桶名称。")
    else:
        # --- 不需要修改下面的内容 ---
        output_prefix = 'ocr_results/'
        gcs_source_uri = f'gs://{bucket_name}/{pdf_file_name}'
        gcs_destination_uri = f'gs://{bucket_name}/{output_prefix}'

        # 调用函数时不再需要传入凭据
        extracted_text = async_detect_document(gcs_source_uri, gcs_destination_uri)

        print("\n\n=============== PDF识别结果 ===============\n")
        print(extracted_text)

        # 将结果保存到Cloud Shell的本地文件中，文件名与原始PDF相同但扩展名为.txt
        output_txt_name = pdf_file_name.rsplit('.', 1)[0] + '.txt'
        with open(output_txt_name, 'w', encoding='utf-8') as f:
            f.write(extracted_text)
        print(f"\n结果已保存到 {output_txt_name} 文件中。")