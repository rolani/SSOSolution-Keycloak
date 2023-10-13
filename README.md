# SSOSolution-Keycloak
Single Sign-On (SSO) solution with Keycloak and Google Workspace. Consolidated user authentication and access control across various applications to significantly enhancing security measures and user experiences.

## Description

Keycloak requires tls to be operational in production, you can create tls certs and upload them as secrets in Kubernetes or use [cert manager](https://github.com/cert-manager/cert-manager) to create a certificate for Keycloak.

You need a running postgresql instance that Keycloak will use (external prefarably for more reliablity).