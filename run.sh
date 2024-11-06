#!/bin/bash

# Start Stable Diffusion WebUI

echo "Starting Stable Diffusion WebUI"

# Check if files are available
if [ -d "/app/sd-webui" ]; then
  echo "Files found, starting..."

  # Move to the WebUI directory
  cd /app/sd-webui

  # Start the WebUI script in the background
  echo "Starting WebUI with arguments: $ARGS"
  ./webui.sh $ARGS &
  webui_pid=$!

  # Activate environment and start run.py in parallel
  echo "Activating environment and starting run.py in parallel..."
  source /app/sd-webui/venv/bin/activate
  python3 /app/onto/run.py --project_id "$PROJECT_ID" --s3_bucket_name "$S3_BUCKET_NAME" --project_name "$PROJECT_NAME"
  run_exit_code=$?

  # Once run.py finishes, check if the WebUI process is still running using `kill -0`
  if kill -0 $webui_pid 2>/dev/null; then
    echo "Stopping WebUI..."
    kill $webui_pid
    wait $webui_pid
  fi

  echo "run.py exited with code $run_exit_code"
  echo "WebUI stopped."

  # Correct permissions
  correct_permissions

  # Exit with the same exit code as run.py
  exit $run_exit_code

else
  echo "Directory /app/sd-webui is missing!"
  exit 1
fi