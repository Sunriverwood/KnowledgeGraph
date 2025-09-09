# Import the necessary libraries
import google.auth
from google.cloud import vision


def detect_text_gcs(project_id, bucket_name, file_name):
    """
    Detects text in an image file located in Google Cloud Storage,
    explicitly setting the quota project ID in the code.
    """
    # 1. Authenticate and explicitly set the quota project.
    # This is the most reliable way to solve the "quota project" error without
    # needing to set environment variables.
    credentials, _ = google.auth.default(quota_project_id=project_id)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    # 2. Define the image location in Google Cloud Storage
    image_uri = f"gs://{bucket_name}/{file_name}"
    print(f"Starting recognition for image at {image_uri}...")

    image = vision.Image()
    image.source.image_uri = image_uri

    # 3. Call the Vision API using the simpler document_text_detection method
    # This avoids the previous TypeError.
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))

    print("--- Full Text Detected ---")
    print(response.full_text_annotation.text)
    print("--------------------------")

    with open(f"{file_name.rsplit('.', 1)[0]}.txt", "w", encoding="utf-8") as f:
        f.write(response.full_text_annotation.text)
    print(f"识别结果已保存为 {file_name.rsplit('.', 1)[0]}.txt")


# --- Main Program ---
if __name__ == '__main__':
    # (Required) Your Google Cloud project ID
    project_id = "valid-octagon-471507-m6"

    # (Required) The name of your GCS storage bucket
    bucket_name = "myocr-project-1"

    # (Required) The filename of the image you uploaded to the bucket
    file_name = "1.png"

    # Check if the user has updated the placeholder values
    if bucket_name == "your-bucket-name-here":
        print("Error: Please update the 'bucket_name' variable in the code with your actual bucket name.")
    else:
        detect_text_gcs(project_id, bucket_name, file_name)