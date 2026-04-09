#!/bin/bash
set -e

# If a kubeconfig exists, we need to patch 127.0.0.1 to host.docker.internal
# so that the container can reach the Kind cluster running on the Windows host.
if [ -f "/root/.kube/config" ]; then
    echo "Found Kubeconfig. Patching 127.0.0.1 to host.docker.internal..."
    mkdir -p /tmp/.kube
    cp /root/.kube/config /tmp/.kube/config
    # Replace 127.0.0.1 with host.docker.internal
    sed -i 's/127.0.0.1/host.docker.internal/g' /tmp/.kube/config
    # Point the environment variable to the patched config
    export KUBECONFIG=/tmp/.kube/config
    echo "KUBECONFIG patched and exported to $KUBECONFIG"
else
    echo "No Kubeconfig found at /root/.kube/config. Skipping patch."
fi

# Run the CMD
exec "$@"
