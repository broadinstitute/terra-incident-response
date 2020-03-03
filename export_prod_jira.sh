#!/bin/bash

JIRA_ISSUE=${1}
VAULT_TOKEN=${2:-$(cat ~/.vault-token)}
#JIRA_TOKEN=`docker run -e VAULT_TOKEN=$VAULT_TOKEN broadinstitute/dsde-toolbox vault read --format=json secret/dsde/firecloud/dev/common/jira.conf | jq -r .data.jira_token`
#JIRA_USER=jenkins-jira@broad.mit.edu
JIRA_TOKEN=$(cat ~/.jira-api-token)
JIRA_USER=jroberti@broadinstitute.org

docker run -e VAULT_TOKEN=$VAULT_TOKEN broadinstitute/dsde-toolbox vault read --format=json secret/dsde/terra/slas/jenkins-automation-service-account.json | jq -r .data > svcacct.json
python parse_jira_issues.py --apiUser $JIRA_USER --apiToken $JIRA_TOKEN --issue $JIRA_ISSUE --bigquerySvcAcct svcacct.json
