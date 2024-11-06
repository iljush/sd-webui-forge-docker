from urllib.parse import urlparse
import boto3
import os
from botocore.exceptions import NoCredentialsError
import requests
import traceback
import time
import glob
import shutil
import logging
from moviepy.editor import ImageSequenceClip, AudioFileClip
import re
logger = logging.getLogger('my_project')

class aws_ingest:
    def __init__(self, username, password, statusUpdateURL, login_url="https://api.app.ontoworks.org/account/login"):
        self.username = username
        self.password = password
        self.login_url = login_url
        self.statusUpdateURL = statusUpdateURL
        self.get_new_token()
        self.projectID = self.extract_project_id(statusUpdateURL)
        self.completedUpdateID = "A4bd50c1-44d0-4614-aa28-ba1a4f767f25"  # Assuming "Completed"
        self.failedUpdateID = "37d6782f-1c3b-46d5-9378-ff85814bc60d"  # Assuming "Failed"

    def get_new_token(self):
        print("Generating new token")
        credentials = {"username": self.username, "password": self.password}
        response = requests.post(self.login_url, json=credentials)
        response.raise_for_status()  # Raises an HTTPError if the response status code is 4XX/5XX
        self.token = response.json()["token"]
        print("New token generated: ", self.token)
    
    def make_request_with_retries(self, request_func, retries=3, backoff_factor=1.0):
        for attempt in range(retries):
            try:
                response = request_func(self.token)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as http_err:
                if http_err.response.status_code == 401:  # Unauthorized, token might have expired
                    logger.error(f'Token expired on attempt {attempt + 1}/{retries}: {http_err}')
                    if attempt < retries - 1:
                        self.get_new_token()
                        logger.info(f'Retrying with new token: {self.token}')
                        time.sleep(backoff_factor * (2 ** attempt))
                    else:
                        return None
                else:
                    logger.error(f'HTTP error occurred on attempt {attempt + 1}/{retries}: {http_err}')
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                    else:
                        return None
            except Exception as err:
                logger.error(f'Other error on attempt {attempt + 1}/{retries}: {err}')
                traceback.print_exc()
                if attempt < retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))
                else:
                    return None

    def update_project_status(self, video_file_name, error_message="", success=True):
        status_id = self.completedUpdateID if success else self.failedUpdateID
        request_func = lambda token: self._send_update_request(token, status_id, video_file_name, error_message)
        return self.make_request_with_retries(request_func)

    def _send_update_request(self, token, status_id, video_file_name, error_message):
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "StatusId": status_id,
            "ErrorMessage": error_message,
            "VideoFileName": video_file_name
        }
        return requests.patch(self.statusUpdateURL, json=payload, headers=headers, verify=False)

    def update_project_percentage(self, percentage):
        request_func = lambda token: self._send_percentage_update_request(token, percentage)
        response = self.make_request_with_retries(request_func)
        if response is None:
            print("Failed to update project percentage after retries.")
        return response

    def _send_percentage_update_request(self, token, percentage):
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {"Percentage": percentage}
        api_url = f"https://api.app.ontoworks.org/project/{self.projectID}/percentage"
        return requests.patch(api_url, json=payload, headers=headers, verify=False)

    def extract_project_id(self, url):
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        try:
            project_id = path_parts[path_parts.index('project') + 1]
            return project_id
        except (ValueError, IndexError):
            raise ValueError("Invalid URL: cannot extract project ID")
    def stitch_video(self, bucket_name, folder_path, video_file_name, output_path, audio_path):
        # Define the directory containing your frames
        frames_dir = folder_path  # update this with your frames directory
        pattern = re.compile(r".*_(\d+)\.png")
        frames = sorted(
            [os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if pattern.match(f)],
            key=lambda x: int(pattern.search(x).group(1))  # Sort by frame ID in the filename
        )
 

        # Load image sequence
        fps = 30  # frames per second
        clip = ImageSequenceClip(frames, fps=fps)

        # Add audio to the clip
        audio = AudioFileClip(audio_path)
        final_clip = clip.set_audio(audio)

        # Save the video
        stitched_video_path = folder_path + video_file_name
        final_clip.write_videofile(stitched_video_path, codec='libx264', audio_codec='aac')
               # Initialize the S3 client
        s3 = boto3.client('s3')

        # Full path to the video file
        files = glob.glob(stitched_video_path)
        if not files:
            print("No MP4 files found in the folder.")
            return None
        original_video_file_path = files[0]
        print("Original video file: ", original_video_file_path)

        # Path with the new name
        new_video_file_path = os.path.join(folder_path, video_file_name)

        # Rename the file
        os.rename(original_video_file_path, new_video_file_path)
        print(f"Renamed file to {new_video_file_path}")

        try:
            # Upload the video file to S3
            s3.upload_file(new_video_file_path, bucket_name, output_path)
            print(f"Successfully uploaded {video_file_name} to s3://{bucket_name}/{output_path}")

            # Delete all frames in the folder
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                try:
                    if os.path.isfile(file_path) and file_name != video_file_name and not file_name.endswith('.txt'):
                        os.remove(file_path)
                        print(f"Deleted frame {file_name}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"Deleted folder {file_path}")
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
            msg = "success"
            return msg
            # Optionally, you can delete the video file itself after uploading if you no longer need it locally
            # os.remove(video_file_path)
    
        except FileNotFoundError:
            print(f"The file {new_video_file_path} was not found")
            return None
        except NoCredentialsError:
            print("Credentials not available")
            return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None


    def upload_video_and_cleanup_frames(self, bucket_name, folder_path, video_file_name, output_path):
        # Initialize the S3 client
        s3 = boto3.client('s3')

        # Full path to the video file
        files = glob.glob(os.path.join(folder_path, '*.mp4'))
        if not files:
            print("No MP4 files found in the folder.")
            return None
        original_video_file_path = files[0]
        print("Original video file: ", original_video_file_path)

        # Path with the new name
        new_video_file_path = os.path.join(folder_path, video_file_name)

        # Rename the file
        os.rename(original_video_file_path, new_video_file_path)
        print(f"Renamed file to {new_video_file_path}")

        try:
            # Upload the video file to S3
            s3.upload_file(new_video_file_path, bucket_name, output_path)
            print(f"Successfully uploaded {video_file_name} to s3://{bucket_name}/{output_path}")

            # Delete all frames in the folder
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                try:
                    if os.path.isfile(file_path) and file_name != video_file_name and not file_name.endswith('.txt'):
                        os.remove(file_path)
                        print(f"Deleted frame {file_name}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"Deleted folder {file_path}")
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
            msg = "success"
            return msg
            # Optionally, you can delete the video file itself after uploading if you no longer need it locally
            # os.remove(video_file_path)
    
        except FileNotFoundError:
            print(f"The file {new_video_file_path} was not found")
            return None
        except NoCredentialsError:
            print("Credentials not available")
            return None
        except Exception as e:
            print(f"Error occurred: {e}")
            return None

    def download_file_from_s3(self, bucket_name, object_key, local_file_path):
        # Initialize S3 client
        s3_client = boto3.client('s3')

        # Download file
        try:
            s3_client.download_file(bucket_name, object_key, local_file_path)
            print(f"File downloaded successfully to {local_file_path}")
        except Exception as e:
            print(f"Error downloading file: {e}")

    def upload_file_to_s3(self, file_path, bucket_name, object_key):
        # Initialize S3 client
        s3_client = boto3.client('s3')

        # Upload file
        try:
            s3_client.upload_file(file_path, bucket_name, object_key)
            print(f"File uploaded successfully to S3://{bucket_name}/{object_key}")
        except Exception as e:
            print(f"Error uploading file: {e}")
# Initialize logging
logging.basicConfig(level=logging.INFO)

# Example usage
# aws = aws_ingest(username="your_username", password="your_password", statusUpdateURL="https://api.app.ontoworks.org/project/a08ee880-20fc-4815-90b1-a0e447d2535b/status")
# aws.update_project_status("example_video.mp4")
