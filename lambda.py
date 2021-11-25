# -*- coding: utf-8 -*-
import json
import boto3
import urllib3
import logging 

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUCCESS = "SUCCESS"
FAILED = "FAILED"

http = urllib3.PoolManager()

def empty_bucket(bucket_name):
    logger.info("Trying to delete the bucket {0}".format(bucket_name))
    s3_client = boto3.client('s3')
    s3 = boto3.resource('s3')
    try:
        bucket = s3.Bucket(bucket_name).load()
    except ClientError:
        logger.info('1')
        logger.info("Bucket {0} does not exist".format(bucket_name))
        return
    # Check versioning
    response = s3_client.get_bucket_versioning(Bucket=bucket_name)
    status = response.get('Status','')
    if status == 'Enabled':
        response = s3_client.put_bucket_versioning(Bucket=bucket_name,
                                                   VersioningConfiguration={'Status': 'Suspended'})
    paginator = s3_client.get_paginator('list_object_versions')
    page_iterator = paginator.paginate(
        Bucket=bucket_name
    )
    for page in page_iterator:
        if 'DeleteMarkers' in page:
            delete_markers = page['DeleteMarkers']
            if delete_markers is not None:
                for delete_marker in delete_markers:
                    key = delete_marker['Key']
                    versionId = delete_marker['VersionId']
                    s3_client.delete_object(Bucket=bucket_name, Key=key, VersionId=versionId)
        if 'Versions' in page and page['Versions'] is not None:
            versions = page['Versions']
            for version in versions:
                key = version['Key']
                versionId = version['VersionId']
                s3_client.delete_object(Bucket=bucket_name, Key=key, VersionId=versionId)
    object_paginator = s3_client.get_paginator('list_objects_v2')
    page_iterator = object_paginator.paginate(
        Bucket=bucket_name
    )
    for page in page_iterator:
        if 'Contents' in page:
            for content in page['Contents']:
                key = content['Key']
                s3_client.delete_object(Bucket=bucket_name, Key=content['Key'])

    print("Successfully emptied the bucket")
def lambda_handler(event, context):
    try:
        bucket = event['ResourceProperties']['BucketName']
        if event['RequestType'] == 'Delete':
            empty_bucket(bucket)
            send(event, context, SUCCESS, {})
        else:
            send(event, context, SUCCESS, {})
    except Exception as e:
        logger.error(str(e))
        send(event, context, FAILED, {})

def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
    responseUrl = event['ResponseURL']
    responseBody = {
        'Status' : responseStatus,
        'Reason' : reason or "See the details in CloudWatch Log Stream: {}".format(context.log_stream_name),
        'PhysicalResourceId' : physicalResourceId or context.log_stream_name,
        'StackId' : event['StackId'],
        'RequestId' : event['RequestId'],
        'LogicalResourceId' : event['LogicalResourceId'],
        'NoEcho' : noEcho,
        'Data' : responseData
    }
    json_responseBody = json.dumps(responseBody)
    logger.info("Response body:")
    logger.info(json_responseBody)
    headers = {
        'content-type' : '',
        'content-length' : str(len(json_responseBody))
    }
    try:
        response = http.request('PUT', responseUrl, headers=headers, body=json_responseBody)
        print("Status code:", response.status)


    except Exception as e:

        print("send(..) failed executing http.request(..):", e)