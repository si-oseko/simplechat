# lambda/index.py
import json
import os
import urllib.request
import urllib.error

# 外部APIのURLを指定 (ngrok の URL に変更) - OK
EXTERNAL_API_URL = "https://81ae-34-142-185-58.ngrok-free.app/generate"

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event))

        # --- Cognito認証情報の取得 (変更なし) ---
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")

        # --- リクエストボディの解析 (変更なし) ---
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
        print("Calling external API:", EXTERNAL_API_URL)

        # --- urllib.request を使った外部API呼び出し ---
        payload_dict = {
            "prompt": message
        }
        payload_json = json.dumps(payload_dict).encode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true" # 必要に応じて
        }

        req = urllib.request.Request(
            EXTERNAL_API_URL,
            data=payload_json,
            headers=headers,
            method='POST'
        )

        api_response_text = "Sorry, I could not get a response." # ← 初期値設定
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

                # --- 3. 応答テキストの抽出を正しいキーで実行 ---
                api_response_text = api_response_data.get("generated_text", "Sorry, the response format was unexpected.") # ← 正しいキーに修正

        # --- (except ブロックは変更なし) ---
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

        # --- (成功レスポンス返却部分は変更なし) ---
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Amz-Security-Token,ngrok-skip-browser-warning",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": api_response_text # 正しく抽出されたテキストが入る
            })
        }

    # --- (最後の except Exception は変更なし) ---
    except Exception as error:
        print("Error:", str(error))
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Amz-Security-Token,ngrok-skip-browser-warning",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }