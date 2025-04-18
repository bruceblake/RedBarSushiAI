#!/bin/bash
# Script to install and set up act for testing GitHub Actions locally

echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y curl docker.io

echo "Downloading nektos/act..."
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

echo "Creating .actrc file..."
cat > .actrc << 'ACTRC'
-P ubuntu-latest=catthehacker/ubuntu:act-latest
-P ubuntu-20.04=catthehacker/ubuntu:act-20.04
--env-file=.env.test
-s GITHUB_TOKEN=fake-token
-s OPENAI_API_KEY=sk-fake-key
-s TWILIO_ACCOUNT_SID=fake-sid
-s TWILIO_AUTH_TOKEN=fake-token
-s TWILIO_NUMBER=+12345678901
-s TESTING=true
-s DISABLE_OPENAI=true
ACTRC

echo "Creating test environment file..."
cat > .env.test << 'ENVTEST'
TESTING=true
DISABLE_OPENAI=true
DATABASE_URL=sqlite:///:memory:
FLASK_ENV=testing
OPENAI_API_KEY=sk-fake-key
TWILIO_ACCOUNT_SID=fake-sid
TWILIO_AUTH_TOKEN=fake-token
TWILIO_NUMBER=+12345678901
ENVTEST

# Make sure Docker is running
echo "Making sure Docker service is running..."
sudo systemctl start docker || echo "Failed to start Docker, please start it manually"

echo -e "\nInstallation complete!\n"
echo "Usage examples:"
echo "---------------"
echo "Test production verification job:"
echo "  act -j production-verification -W .github/workflows/promote-to-main.yml"
echo ""
echo "Test CI jobs:"
echo "  act -j test -W .github/workflows/ci.yml"
echo "  act -j lint -W .github/workflows/ci.yml"
echo "  act -j e2e-tests -W .github/workflows/ci.yml"
echo ""
echo "Test a specific event:"
echo "  act push"
echo "  act pull_request"
echo ""
echo "Note: You may need to run 'sudo act' depending on your Docker configuration"