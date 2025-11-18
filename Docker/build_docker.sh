#!/bin/bash

docker buildx build --platform linux/amd64,linux/arm64  -f ./Dockerfile -t macielleah/ring_tissue:1.5 --push .


