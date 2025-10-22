import json
import boto3
import os

# Environment variables (to be set in Lambda configuration)
S3_BUCKET = os.environ.get('S3_BUCKET')
FOLDER_NAME = os.environ.get('FOLDER_NAME')
BEDROCK_REGION = os.environ.get('BEDROCK_REGION', 'us-east-1')
CLAUDE_MODEL_ID = os.environ.get('CLAUDE_MODEL_ID')
bedrock_agent = boto3.client('bedrock-agent-runtime')
def call_bedrock_claude(prompt):
    bedrock = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 5000,
        "temperature": 0.7,
        "messages": [
            {"role": "user", "content": f"\n\nHuman: {prompt}\n\nAssistant:"}
        ]
    }

    response = bedrock.invoke_model(
        modelId=CLAUDE_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body)
    )

    result = json.loads(response['body'].read())
    model_output = result["content"][0]["text"]
    print(f"AI Response: {model_output}")
    return result.get('completion', '')

def read_incident_files_from_s3(bucket_name, folder_name):
    s3 = boto3.client('s3')
    incidents = []

    # List all objects in the bucket
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)
    for obj in response.get('Contents', []):
        key = obj['Key']
        # print("Key:->", key)
        # Read each file content
        file_obj = s3.get_object(Bucket=bucket_name, Key=key)
        content = file_obj['Body'].read().decode('utf-8')
        # print("content:->", content)
        if content:
            incidents.append({"file_name": key, "content": content})
    # print("incidents:->", incidents)
    return incidents

def read_json_from_s3(bucket_name, folder_path, file_name):
    """
    Reads a JSON file from a given S3 bucket and folder.

    Args:
        bucket_name (str): Name of the S3 bucket.
        folder_path (str): Folder path inside the bucket (without leading slash).
        file_name (str): JSON file name (e.g., 'data.json').

    Returns:
        dict: Parsed JSON content from the file.
    """

    s3 = boto3.client("s3")

    # Build full key (path to the file)
    s3_key = f"{folder_path}/{file_name}"

    try:
        # Fetch the object from S3
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)

        # Read and decode file content
        content = response["Body"].read().decode("utf-8")

        # Parse JSON content
        data = json.loads(content)

        return data

    except Exception as e:
        print(f"Error reading {s3_key} from {bucket_name}: {e}")
        return None

def lambda_handler(event, context):
    # Read incident files from S3
    context_file = read_json_from_s3(S3_BUCKET, 'context', 'servicenow_tickets_with_resolution.json')
    incident_files = read_incident_files_from_s3(S3_BUCKET, FOLDER_NAME)
    results = []

    for incident in incident_files:
        # prompt = f"Context: {context_file}. Analyze the following IT incident and suggest possible causes and resolutions: {incident['content']}. Return the response with urgncy and resolution from the given context."
        # print("context_file:->", context_file)
        # print("incident:->",incident)
        # print("incident['content']:->", incident['content'])
        # prompt = f"""
        # You are an AI assistant. Use the following data as your knowledge base:
        # {context_file}
        # Can you search the description mentioned in {incident['content']} inside {context_file} and return all other mathcing field?
        # Now Analyze the following IT incident and suggest possible causes and resolutions: {incident['content']}
        # Also calculate the priority and urgency of the incident.
        # """
        # ai_response = call_bedrock_claude(prompt)
        prompt = f"""
        Can you search the description mentioned in {incident['content']} return all other mathcing field?
        Analyze the following IT incident and suggest possible causes and resolutions: {incident['content']}
        Also calculate the priority and urgency of the incident.
        """        
        ai_response = bedrock_agent.retrieve_and_generate(
            input={"text": prompt},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": "K34B3RLR4C",
                    "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
                }   
            }
        )
        print("ai_response",ai_response)
        results.append({
            "file": incident['file_name'],
            "incident": incident['content'],
            "ai_analysis": ai_response
        })


    return {
        "statusCode": 200,
        "body": json.dumps(results)
    }
