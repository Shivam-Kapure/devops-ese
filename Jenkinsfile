// UPI Payment Settlement Engine - local demonstration pipeline.
// Runs on the Windows Jenkins agent (service account LocalSystem), so all shell steps use `bat`.
// Job type: "Pipeline script from SCM" - every stage works on the files Jenkins checked out from Git.
pipeline {
    agent any

    environment {
        IMAGE_NAME     = 'fintech-gateway:v1.0'
        BACKEND_IMAGE  = 'upi-settlement-backend:v1.0'
        FRONTEND_IMAGE = 'upi-settlement-frontend:v1.0'
    }

    stages {
        stage('Build & Unit Test') {
            steps {
                echo 'Payment settlement build & unit-test stage is running...'
                echo "Source: ${env.GIT_URL ?: 'n/a'} @ ${env.GIT_COMMIT ?: 'n/a'}"
                echo 'Step 1/2: deterministic validation of gateway.conf'
                bat '''
                    @echo off
                    if not exist gateway.conf (
                        echo FAIL: gateway.conf not found
                        exit /b 1
                    )
                    rem Joining all lines must give exactly the one required line (works for LF or CRLF endings)
                    powershell -NoProfile -NonInteractive -Command "if (((Get-Content gateway.conf) -join '|') -ne 'SETTLEMENT_CORE=ACTIVE') { exit 1 }" || (
                        echo FAIL: gateway.conf must contain exactly the single line SETTLEMENT_CORE=ACTIVE
                        exit /b 1
                    )
                    if not exist Dockerfile (
                        echo FAIL: Dockerfile not found
                        exit /b 1
                    )
                    echo PASS: gateway.conf contains exactly SETTLEMENT_CORE=ACTIVE
                    echo PASS: Dockerfile present
                '''
                // Tests run inside the backend image's `test` stage, so the agent needs Docker but no local Python packages.
                echo 'Step 2/2: settlement backend unit tests (pytest, Docker test stage)'
                bat '''
                    @echo off
                    rem --no-cache-filter test: always re-run pytest instead of reusing a cached test layer
                    docker build --progress=plain --no-cache-filter test --target test -t upi-settlement-backend:test backend || (
                        echo FAIL: backend unit tests failed
                        exit /b 1
                    )
                    echo PASS: backend unit tests
                '''
            }
        }

        stage('Docker Build') {
            steps {
                bat '''
                    @echo off
                    docker build -t %IMAGE_NAME% . || exit /b 1
                    docker image inspect %IMAGE_NAME% --format "Image %IMAGE_NAME% ID={{.Id}} Created={{.Created}}" || exit /b 1
                    docker build --target runtime -t %BACKEND_IMAGE% backend || exit /b 1
                    docker image inspect %BACKEND_IMAGE% --format "Image %BACKEND_IMAGE% ID={{.Id}}" || exit /b 1
                    docker build -t %FRONTEND_IMAGE% frontend || exit /b 1
                    docker image inspect %FRONTEND_IMAGE% --format "Image %FRONTEND_IMAGE% ID={{.Id}}" || exit /b 1
                '''
            }
        }

        stage('Cluster Deploy') {
            steps {
                echo 'Kubernetes deployment stage is running...'
                echo 'Demonstration only: this pipeline does NOT apply Kubernetes manifests.'
                echo 'Manifests applied manually after approval: payment-k8s.yaml (payment-deployment / payment-service, NodePort 30091)'
                echo 'and k8s/app-k8s.yaml (settlement-backend / settlement-frontend, NodePort 30092).'
            }
        }
    }

    post {
        success { echo 'Payment settlement pipeline completed successfully.' }
        failure { echo 'Payment settlement pipeline failed - see the failing stage above.' }
    }
}
