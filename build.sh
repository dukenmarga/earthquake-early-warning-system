gcloud builds submit --config cloudbuild_run.yaml --project nutmeg-435109
gcloud run deploy earthquake-warning-system --platform managed --region asia-southeast2 --image gcr.io/nutmeg-435109/earthquake-warning-system --allow-unauthenticated --project nutmeg-435109
gcloud run services update earthquake-warning-system --project nutmeg-435109 --session-affinity