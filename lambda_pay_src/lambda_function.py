import json
from botocore.exceptions import ClientError
import requests
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import boto3


def get_secret():
    print("get cred")
    secret_name = "bill-calculator-sheet-cred"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    print("get cred2")
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    print("get cred3")

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        print("get cred4")
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    secret_json = json.loads(secret)
    print("get cred finished")
    return secret_json


def get_sheet():
    SHEET_ID = "1gkVUAVPc7NXV1FBe1b9tp-3x8KcvUEr_BLV5n-wdBco"

    scope = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file'
    ]
    SCOPES = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
              "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    secret_dict = get_secret()
    print(secret_dict)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(secret_dict, scope)
    print("get sheet")
    client = gspread.authorize(creds)
    print("get sheet authed")

    print(requests.get("https://phet-dev.colorado.edu/html/build-an-atom/0.0.0-3/simple-text-only-test-page.html"))
    now = datetime.now()

    current_time = now.strftime("%H:%M:%S")
    print(current_time)
    sheet = client.open_by_key(SHEET_ID).sheet1
    print(current_time)
    python_sheet = sheet.get_all_records()
    print("sheet got")
    return python_sheet, sheet


def lambda_handler(event, context):
    json_request = event

    from_who = json_request.get("from")
    to_who = json_request.get("to")
    amount = json_request.get("amount")

    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # date, from, to, product, price, tax_flg, who, type
    result = [time_now, from_who, to_who, "进行一个钱的还💰", amount, None, None, "pay"]


    sheet_content, sheet = get_sheet()
    sheet.append_row(result, table_range="A1:H1")

    return {
        "statusCode": 200,
        "body": str(result),
        "headers": {
            "Content-Type": 'application/json',
        }
    }


if __name__ == '__main__':
    print(lambda_handler("", "")["body"])