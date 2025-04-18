#!/bin/bash
# Script to install and set up act for testing GitHub Actions locally

echo "Installing act locally instead of globally..."

# Create local bin directory
mkdir -p bin

echo "Downloading act binary..."
# Directly download the latest release binary
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

if [[ "$ARCH" == "x86_64" ]]; then
  ARCH="amd64"
elif [[ "$ARCH" == "aarch64" ]]; then
  ARCH="arm64"
fi

# Install act locally 
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh > bin/install-act.sh
chmod +x bin/install-act.sh
(cd bin && ./install-act.sh)

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

echo -e "\nSetup complete!\n"
echo "Usage examples:"
echo "---------------"
echo "Test production verification job:"
echo "  ./bin/act -j production-verification -W .github/workflows/promote-to-main.yml"
echo ""
echo "Test CI jobs:"
echo "  ./bin/act -j test -W .github/workflows/ci.yml"
echo "  ./bin/act -j lint -W .github/workflows/ci.yml"
echo "  ./bin/act -j e2e-tests -W .github/workflows/ci.yml"
echo ""
echo "Test a specific event:"
echo "  ./bin/act push"
echo "  ./bin/act pull_request"
echo ""
echo "Note: Docker must be running to use act"