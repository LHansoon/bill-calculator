# bill-calculator

you will need to have a Google service account and have editor access granted, the credentials.json will contain the required information generated by Google Cloud Service, containing information like type, project_id, private_key_id, private_key, client_email, client_id, auth_uri, token_uri, auth_provider_x509_cert_url, client_x509_cert_url

This is a local deployment software and shouldn't be exposed to public internet since there is no security sys implemented and the implementation never considers the security issue:

It might work, but it's not safe.


## config

in src: python app.py 8000

config file template:

config.json in src
```
{
    "sheet_id": "***********",
    "cred_path": "credentials.json",
    "tax_rate": 0.15,
    "money_return_msg": "Money Trans💰",
    "port": 8000
}
```

## description
The software provided service to auto calculate the debt and money transfer procedure required to make everybody clear on bills

A paid 10 dollars for B and C, and B paid 5 dollars for A, C paid 6 dollars for B and A, in the regular procedure, we would need:
- B and C ===$5===> A
- A       ===$5===> B
- B and A ===$3===> C

but the software will optimize the debt and tell you:
- B       ===$1===> C
- B       ===$2===> A

The software uses Google Sheets as the data source due to its easy to understand and edit nature.



### Example:
<img width="1581" alt="Screenshot 2023-10-16 at 8 02 10 PM" src="https://github.com/LHansoon/bill-calculator/assets/76853769/761f3073-1816-4b24-8f35-425ce8fda126">


### Interface:
<img width="1600" alt="Screenshot 2023-10-16 at 7 57 32 PM" src="https://github.com/LHansoon/bill-calculator/assets/76853769/3dbc918b-85a5-4a93-8a47-dab72d74e86f">
