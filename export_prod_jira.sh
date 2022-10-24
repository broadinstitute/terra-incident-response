#!/bin/bash

JIRA_ISSUE=${1}
VAULT_TOKEN=${2:-$(cat ~/.vault-token)}
JIRA_TOKEN=$(vault read --format=json secret/dsde/firecloud/dev/common/jira.conf | jq -r .data.jira_token)
JIRA_USER=jenkins-jira@broad.mit.edu


vault read --format=json secret/dsde/terra/slas/jenkins-automation-service-account.json | jq -r .data > svcacct.json

# Run locally (default)
python parse_jira_issues.py --apiUser ${JIRA_USER} --apiToken ${JIRA_TOKEN} --issue ${JIRA_ISSUE} --bigquerySvcAcct svcacct.json

# Run in docker (for automation)
# docker build -t sla-import .
# docker run -v "$(pwd)"/svcacct.json:/app/svcacct.json sla-import python parse_jira_issues.py --apiUser ${JIRA_USER} --apiToken ${JIRA_TOKEN} --issue ${JIRA_ISSUE} --bigquerySvcAcct svcacct.json
