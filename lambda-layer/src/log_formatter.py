import os
from aws_lambda_powertools.logging.formatter import (
    BasePowertoolsFormatter,
    LambdaPowertoolsFormatter,
)
from aws_lambda_powertools.logging.types import LogRecord


class CustomFormatter(LambdaPowertoolsFormatter):
    def serialize(self, log: LogRecord) -> str:
        """Serialize final structured log dict to JSON str"""

        log = {
            "logLevel": log.get("level",None),
            "message": log.get("message",None),
            "environment": os.environ["ENVIRONMENT"],
            "awsRegion": os.environ["AWS_REGION"],
            "correlationIds": {
                "awsRequestId": log.get("correlation_id",{}).get("awsRequestId",None),
                "xRayTraceId": log.get("xray_trace_id",None),
            },
            "lambdaFunction": {
                "name": log.get("function_name",None),
                "arn": log.get("function_arn",None),
                "memoryLimitInMB": log.get("function_memory_size",None),
                "version": os.getenv("AWS_LAMBDA_FUNCTION_VERSION", "$LATEST"),
                "coldStart": log.get("cold_start",None)
            },
            "timestamp": log.get("timestamp",None),
            "logger": {
                "sampleRateValue": log.get("sample_rate_value",None)
            }
        }
        return self.json_serializer(log)