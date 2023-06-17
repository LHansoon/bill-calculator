# IMPORTANT: You MUST run the script in the lambda sub dir (ex. new-job-controller/)

pack_name="lambda-pack.zip"

echo Preparing the venv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt --quiet
./venv/bin/pip install --user --upgrade --force-reinstall numpy

echo Packing up the zip
curr_dir=`pwd`
(cd venv/lib/python3.9/site-packages && zip -r $curr_dir/$pack_name .)
zip -r $pack_name lambda_function.py
zip -g $pack_name config.json
zip -g $pack_name home.html

echo Deleting the venv
rm -rf venv

aws lambda update-function-code --function-name bill-calculator-lambda --zip-file fileb://$pack_name
rm $pack_name