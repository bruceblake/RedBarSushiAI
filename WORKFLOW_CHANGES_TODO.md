# GitHub Workflow Changes TODO

The following changes need to be applied to `.github/workflows/ci.yml` once you update your Personal Access Token with the `workflow` scope:

## How to Update Your Token

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token or update existing one
3. Make sure to check the `workflow` scope
4. Update your Git credentials with the new token

## Changes to Apply

In `.github/workflows/ci.yml`, replace the `docker-integration-tests` job (starting around line 130) with:

```yaml
  docker-tests:
    runs-on: ubuntu-latest
    needs: build-and-test
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
      
    - name: Create .env file
      run: |
        echo "OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}" >> .env
        echo "TWILIO_ACCOUNT_SID=${{ secrets.TWILIO_ACCOUNT_SID }}" >> .env
        echo "TWILIO_AUTH_TOKEN=${{ secrets.TWILIO_AUTH_TOKEN }}" >> .env
        echo "DELIVERECT_API_KEY=${{ secrets.DELIVERECT_API_KEY }}" >> .env
        
    - name: Run unit tests in Docker
      run: |
        ./run-docker-tests.sh unit
      
    - name: Run integration tests in Docker
      run: |
        ./run-docker-tests.sh integration
        
    - name: Run E2E tests in Docker
      run: |
        ./run-docker-tests.sh e2e
        
    - name: Stop Docker containers
      if: always()
      run: |
        docker-compose down
```

This will enable the CI/CD pipeline to run your comprehensive test suite in Docker.

## Alternative: Manual Workflow Update

If you prefer not to update your token, you can:
1. Edit the workflow file directly in GitHub's web interface
2. Or have a repository admin make these changes