# Shared proxy headers for every Django-backed location.
proxy_http_version 1.1;
# $http_host, not $host: $host drops the port, which would make Django build
# absolute URLs like http://localhost/... in password-reset e-mails when the
# app is published on any port other than 80.
proxy_set_header Host              $http_host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
proxy_set_header Connection        "";
proxy_redirect off;
proxy_connect_timeout 10s;
proxy_read_timeout    60s;
proxy_send_timeout    60s;
