""" Lambda function to be used in the Serverless Patterns Lab-01"""
from typing import Any, Dict, Iterable, List, Optional
import os
import uuid
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from faker import Faker
import boto3
from botocore.exceptions import ClientError, ParamValidationError
from ssm_util import get_ssm_parameter
from dynamodb_util import (
    put_item,
    batch_write_item,
    get_item,
    update_item,
    query_items,
    delete_item,
    scan_items,
    get_item_count,
)
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    Response,
)
from aws_lambda_powertools.logging import correlation_paths
from log_formatter import CustomFormatter

logger = Logger(
    service="serverless-lab-01",
    sample_rate_value=0.1,
    logger_formatter=CustomFormatter(),
)
tracer = Tracer(service="serverless-lab-01")
app = APIGatewayRestResolver()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])
dynamodb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"])
DYNAMODB_TABLE_NAME = get_ssm_parameter(
    ssm_client=ssm_client,
    name=f"/{os.environ['PROJECT_NAME']}/{os.environ['ENVIRONMENT']}/dynamodb-table-name",
    logger=logger,
    tracer=tracer,
)


@app.get("/users")
def get_users():
    """
    Get the user from the DynamoDB
    """

    query_string_parameters = app.current_event.query_string_parameters
    partition_key = query_string_parameters["user_id"]
    logger.info({"id": partition_key})

    response = get_item(
        dynamodb_client=dynamodb_client,
        table_name=DYNAMODB_TABLE_NAME,
        key={
            "_id": {
                "S": partition_key,
            }
        },
        logger=logger,
    )
    status_code = 200 ##response["ResponseMetadata"]["HTTPStatusCode"]
    if status_code != 200:
        status_code = 400
    return {
        "statusCode": status_code,
        "isBase64Encoded": False,
        "body": {
            "item": response or "No matching item found",
        },
    }


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    AWS Lambda function handler
    """
    return app.resolve(event, context)
