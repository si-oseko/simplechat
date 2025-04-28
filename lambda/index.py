# lambda/index.py
import json
import os
import urllib.request
import urllib.error
# import re # Bedrock関連を使わないなら不要
# import boto3 # Bedrock関連を使わないなら不要
# from botocore.exceptions import ClientError # Bedrock関連を使わないなら不要

# 外部APIのURLを指定 (ngrok の URL に変更)
EXTERNAL_API_URL = "https://7071-35-240-222-95.ngrok-free.app/chat"

# --- BedrockクライアントやMODEL_IDは不要 ---
# bedrock_client = None
# MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")
# def extract_region_from_arn(arn): ... も不要

def lambda_handler(event, context):
    try:
        # --- Bedrockクライアント初期化は不要 ---
        # global bedrock_client
        # ...

        print("Received event:", json.dumps(event))

        # --- Cognito認証情報の取得は元のコードから流用可能 (必要なら) ---
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")

        # リクエストボディの解析 (元のコードと同じ)
        try:
            body = json.loads(event['body'])
            message = body['message']
            if not message:
                raise ValueError("message cannot be empty")
        except (TypeError, KeyError, json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse request body or message is missing/empty: {e}")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"success": False, "error": "Invalid request body or missing/empty 'message'"})
            }

        print("Received message (prompt):", message)
        print("Calling external API:", EXTERNAL_API_URL) # ここで指定したURLが表示される

        # --- ここから urllib.request を使った外部API呼び出し (Bedrock部分を置き換え) ---
        payload_dict = {
            "prompt": message # シンプルな形式に変更済み
        }
        payload_json = json.dumps(payload_dict).encode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true" # 必要に応じて
        }
        # 認証不要なのでAPIキー関連は削除済み

        req = urllib.request.Request(
            EXTERNAL_API_URL,
            data=payload_json,
            headers=headers,
            method='POST'
        )

        api_response_text = "Sorry, I could not get a response."
        api_response_data = None
        response_body_str = ""

        try:
            timeout_seconds = 15
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                status_code = response.getcode()
                print(f"External API status code: {status_code}")

                if not (200 <= status_code < 300):
                    error_reason = f"API returned non-2xx status: {status_code}"
                    try:
                        error_body_preview = response.read(512).decode('utf-8', errors='ignore')
                        print(f"Error response preview: {error_body_preview}")
                        if "ngrok" in error_body_preview.lower() and "failed to connect" in error_body_preview.lower():
                            error_reason = "ngrok tunnel is not running or failed to connect to the local service"
                        elif "tunnel" in error_body_preview.lower() and "not found" in error_body_preview.lower():
                             error_reason = "ngrok tunnel not found (URL might be wrong or expired)"
                    except Exception:
                        pass
                    raise urllib.error.HTTPError(
                        req.full_url, status_code, error_reason, response.headers, response)

                response_body_bytes = response.read()
                response_body_str = response_body_bytes.decode('utf-8')
                api_response_data = json.loads(response_body_str)
                print("External API response:", json.dumps(api_response_data, default=str))

                # APIの応答形式に合わせて調整
                api_response_text = api_response_data.get("completion") or api_response_data.get("response", "Sorry, the response format was unexpected.")

        # (以下、エラーハンドリングとレスポンス返却部分は前の回答と同じ)
        except urllib.error.HTTPError as e:
            print(f"HTTP Error calling external API: {e.code} {e.reason}")
            try:
                error_body = e.read().decode('utf-8')
                print(f"Error response body: {error_body}")
            except Exception as read_err:
                print(f"Could not read error response body: {read_err}")
            raise Exception(f"External API request failed: {e.reason} (HTTP {e.code})")

        except urllib.error.URLError as e:
            print(f"URL Error calling external API: {e.reason}")
            raise Exception(f"Network error communicating with the external API: {e.reason}")

        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON response from API: {e}")
            print(f"Raw response (first 500 chars): {response_body_str[:500]}...")
            if "ngrok" in response_body_str.lower():
                 raise Exception("Received an ngrok page instead of API response. Check if the tunnel is active and points to the correct service.")
            else:
                raise Exception("Received invalid JSON response from the external API.")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise Exception(f"An unexpected error occurred while calling the external API: {e}")
        # --- 外部API呼び出しここまで ---

        # --- 会話履歴の処理は削除 (シンプルな応答) ---
        # messages = conversation_history.copy()
        # messages.append(...)

        # 成功レスポンスの返却 (シンプル版)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Amz-Security-Token,ngrok-skip-browser-warning", # 認証不要なら X-Api-Key は削除
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": api_response_text
            })
        }

    except Exception as error:
        print("Error:", str(error))
        # (エラーレスポンス部分は元のコードと同様)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,ngrok-skip-browser-warning",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }