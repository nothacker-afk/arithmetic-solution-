# Arithmetic Super App — Helm chart

## Install

    helm install arith ./helm/arithmetic -n arithmetic --create-namespace

## Upgrade

    helm upgrade arith ./helm/arithmetic -n arithmetic

## Customize

    helm install arith ./helm/arithmetic \
        --set image.repository=your-registry/arithmetic-super-app \
        --set image.tag=v0.21.0 \
        --set ingress.hosts[0].host=arith.example.com \
        --set secrets.jwtSecret=$(python -c 'import secrets;print(secrets.token_hex(32))')

## Uninstall

    helm uninstall arith -n arithmetic

## Raw manifests

For `kubectl apply` without Helm:

    kubectl apply -f k8s/namespace.yaml
    kubectl apply -f k8s/secret.yaml            # from secret.yaml.example
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/pvc.yaml
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml
    kubectl apply -f k8s/ingress.yaml
