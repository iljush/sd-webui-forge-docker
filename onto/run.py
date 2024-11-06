
from datetime import datetime
import requests
import traceback
import json
import time
import argparse
from aws_ingest import aws_ingest
import os
import sys


# Base URL of the API
BASE_URL = "http://127.0.0.1:7860"

def load_deforum_settings(file_path):
    with open(file_path, "r") as file:
        deforum_settings = json.load(file)
    return deforum_settings


# Function to get the list of batches
def get_batches():
    url = f"{BASE_URL}/deforum_api/batches"
    response = requests.get(url)
    return response.json()

# Function to get the list of jobs
def get_jobs():
    url = f"{BASE_URL}/deforum_api/jobs"
    response = requests.get(url)
    return response.json()

# Function to get the status of a specific job
def get_job_status(job_id):
    url = f"{BASE_URL}/deforum_api/jobs/{job_id}"
    response = requests.get(url)
    return response.json()

# Function to delete a specific job
def delete_job(job_id):
    url = f"{BASE_URL}/deforum_api/jobs/{job_id}"
    response = requests.delete(url)
    return response.json()

def is_api_running():
    url = f"{BASE_URL}/deforum_api/batches"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
        else:
            return False, response.status_code
    except requests.exceptions.RequestException as e:
        return False


# Function to create a batch of jobs
def create_batch(deforum_settings, settings_overrides=None):
    url = f"{BASE_URL}/deforum_api/batches"
    payload = {
        "deforum_settings": deforum_settings,
        "options_overrides": settings_overrides or {}
    }
    if settings_overrides:
        payload["settings_overrides"] = settings_overrides

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raises HTTPError for bad responses
        response_json = response.json()
        if "job_ids" not in response_json:
            raise ValueError(f"Response does not contain 'job_ids': {response_json}")
        return response_json
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e} - Response content: {response.content}")
        raise
    except Exception as e:
        print(f"An error occurred while creating batch: {e}")
        raise

# Modify the attempt_create_batch_with_retries function
def attempt_create_batch_with_retries(deforum_settings, retries=100, backoff_factor=15):
    for attempt in range(retries):
        try:
            response = create_batch(deforum_settings)
            print('Created Batch Response.')
            return response
        except Exception as e:
            print(f'Error on attempt {attempt + 1}/{retries}: {e}')
            if attempt < retries - 1:
                sleep_time = backoff_factor
                print(f'Waiting for {sleep_time} seconds before next attempt...')
                time.sleep(sleep_time)
            else:
                print(f'Failed to create batch after {retries} attempts.')
                return None


def get_job_status_with_retries(job_id, retries=5, backoff_factor=5):
    for attempt in range(retries):
        try:
            response = get_job_status(job_id)
            return response
        except requests.exceptions.RequestException as e:
            print(f'Error getting job status: {e}')
            if attempt < retries - 1:
                sleep_time = backoff_factor * (attempt + 1)
                print(f'Retrying in {sleep_time} seconds...')
                time.sleep(sleep_time)
            else:
                print(f'Failed to get job status after {retries} attempts.')
                raise

if __name__ == "__main__":
   

    
    start_time = datetime.now()
    start_process_time = time.time()
    
    current_dir =  os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Music Video Generation")
    parser.add_argument(
        "--project_id",
        type=str,
        default="b605ae50-515a-49fd-a81e-ef465ab8da5a",
        help="Name of the S3 bucket where audio and submitted form are stored"
    )
    parser.add_argument(
        "--s3_bucket_name",
        type=str,
        default="blob.api.app.ontoworks.org",
        help="Name of the S3 bucket where audio and submitted form are stored"
    )
    parser.add_argument(
        "--project_name",
        type=str,
        default="Project",
        help="name of the video file that the user can download"
    )
    args = parser.parse_args()

    #Project-specific API URL
    update_api_url = f"https://api.app.ontoworks.org/project/{args.project_id}/status"
    #Object key of the audio file stored in S3 bucket
    audio_object_key=f"Project.Audio/{args.project_id}"
    #Object key of the deforum settings stored in S3 bucket
    deforum_settings_object_key=f"Project.Finalized.Settings/{args.project_id}"
    #Path on EC2 where audio is downloaded to
    local_audio_path = os.path.join(current_dir, "audio.mp3")
    #Path on EC2 where deforum settings is downloaded to
    local_settings_path = os.path.join(current_dir,"deforum.json")
    #Path where video will be uploaded.
    upload_video_path  = f"Project.Output/{args.project_id}"
 


    aws_api = aws_ingest( "api@ontoworks.org" , "Ontoworks@123",update_api_url)

    aws_api.download_file_from_s3(args.s3_bucket_name, audio_object_key,local_audio_path)
    aws_api.download_file_from_s3(args.s3_bucket_name, deforum_settings_object_key, local_settings_path)

    video_file_name= args.project_name + ".mp4" #"_" + combined_form['batch_name'][8:] +'.mp4'

   

    deforum_settings = load_deforum_settings(local_settings_path)
    deforum_settings["soundtrack_path"] = local_audio_path
    deforum_settings["batch_name"] = "deforum"
    max_frames  = deforum_settings["max_frames"]
    # Create a batch of jobs
    response = attempt_create_batch_with_retries(deforum_settings)
    print("Create Batch Response:" + str( json.dumps(response, indent=2)))
    
    
    if response and "job_ids" in response:
        job_id = response["job_ids"][0]
    else:
        print("Failed to retrieve 'job_ids' from the response.")
        sys.exit(1)  # Exit or handle the error appropriately
    estimated_total_time = max_frames * 5
    time.sleep(5)

    try:
        response = get_job_status_with_retries(job_id)

        while not (response["phase"]=="DONE"):
            if (response["status"]=="FAILED"):
                print("Automatic1111 Error")
                status_id = "37d6782f-1c3b-46d5-9378-ff85814bc60d"  # Assuming "Failed"
                update_response = aws_api.update_project_status(  video_file_name, error_message="Automatic1111 Error", success=False)
                print("Project status updated with failure: Automatic1111 Error" + ' \n Project status updated with failure.')
                sys.exit(1)  # Exit code 1 for failure

            time.sleep(15)

            print('Getting Status for job ' + str(job_id))
            response = get_job_status_with_retries(job_id)
            current_process_time = time.time() - start_process_time
            
            phase_progress = float(current_process_time) / estimated_total_time


            awsUpdateResp = aws_api.update_project_percentage(int(phase_progress * 100))            
            print("AWS: "+ str( awsUpdateResp) + "" +"\n status: "+ str(  response["status"]) + "\n phase: " + str( response["phase"])  +'\n phase_progress: ' + str(int(phase_progress * 100)))
    
    except Exception as e:

        print(f"An error occurred: {e}")
        error_message = str(e)
        status_id = "37d6782f-1c3b-46d5-9378-ff85814bc60d"  # Assuming "Failed"
        update_response = aws_api.update_project_status(  video_file_name, error_message=error_message, success=False)
        print("Project status updated with failure:" + str( update_response) + ' \n Project status updated with failure.')
        sys.exit(1)  # Exit code 1 for failure

    bucket_path = args.s3_bucket_name 



    msg = aws_api.stitch_video(bucket_path, "/app/sd-webui/outputs/img2img-images/deforum", video_file_name, upload_video_path,local_audio_path)


    print('project completed.')

    if msg is not None:
        update_response = aws_api.update_project_status( video_file_name)
        print(update_response) 
        print(str(update_response))
    else:
        #FAILED
        update_response = aws_api.update_project_status( video_file_name,error_message="upload of finished video failed :(", success=False)
        print("Project status updated with failure:"+ str(  update_response))
        print('Project status updated with failure.')
        print("Process failed.")
        sys.exit(1)  # Exit code 1 for failure
    
    current_time = datetime.now()
    print("PROJECT FINISHED AT"+ str(  current_time))
    duration = current_time - start_time
    formatted_duration = str(duration).split(".")[0] 
    print(f"TOTAL DURATION: {formatted_duration}")
    print("Process completed successfully.")
    sys.exit(0)  # Exit code 0 for success



