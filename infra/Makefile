updatecredential:
	@cat aws_credential > ~/.aws/credentials


buildworker:
	@docker build --no-cache --platform linux/amd64 -t bill-app -f dockerfile-app ../

pushworker:
	@aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 572010479953.dkr.ecr.us-east-1.amazonaws.com
	@docker tag bill-app 572010479953.dkr.ecr.us-east-1.amazonaws.com/bill-app:latest
	@docker push 572010479953.dkr.ecr.us-east-1.amazonaws.com/bill-app:latest

updateworkerimage: buildworker pushworker