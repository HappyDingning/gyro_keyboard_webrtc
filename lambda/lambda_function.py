import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

# 初始化 DynamoDB
TABLE_NAME = os.environ.get("SIGNAL_TABLE")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    path = event["requestContext"]["http"]["path"]
    method = event["requestContext"]["http"]["method"]

    # 通用 CORS
    headers = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"}

    # 静态资源路由
    if method == "GET" and path == "/default/index.html":
        with open("index.html", "r") as f:
            index_html = f.read()
        return {
            "statusCode": 200,
            "headers": {**headers, "Content-Type": "text/html"},
            "body": index_html,
        }

    if method == "GET" and path == "/default/client.js":
        with open("client.js", "r") as f:
            client_js = f.read()
        return {
            "statusCode": 200,
            "headers": {**headers, "Content-Type": "application/javascript"},
            "body": client_js,
        }

    # 信令接口
    if path == "/default/signal":
        if method == "OPTIONS":
            return {"statusCode": 200, "headers": headers}

        if method == "POST":
            body = json.loads(event.get("body") or "{}")
            item = {
                "to": body["to"],
                "timestamp": int(time.time() * 1000),
                "from": body["from"],
                "type": body["type"],
            }
            if "sdp" in body:
                item["sdp"] = body["sdp"]
            if "candidate" in body:
                item["candidate"] = body["candidate"]
            table.put_item(Item=item)
            return {
                "statusCode": 200,
                "headers": {**headers, "Content-Type": "application/json"},
                "body": json.dumps({"result": "ok"}),
            }

        if method == "GET":
            params = event.get("queryStringParameters") or {}
            client_id = params.get("clientId")
            if not client_id:
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": "Missing clientId",
                }

            resp = table.query(KeyConditionExpression=Key("to").eq(client_id))
            items = resp.get("Items", [])

            # convert timestamp to int
            for it in items:
                it["timestamp"] = int(it["timestamp"])

            items.sort(key=lambda x: x["timestamp"])

            with table.batch_writer() as batch:
                for it in items:
                    batch.delete_item(
                        Key={"to": it["to"], "timestamp": it["timestamp"]}
                    )

            return {
                "statusCode": 200,
                "headers": {**headers, "Content-Type": "application/json"},
                "body": json.dumps(items),
            }

    return {
        "statusCode": 405,
        "headers": headers,
        "body": "Method Not Allowed",
    }
