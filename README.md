# Terra Incident Response tracking

Terra's Service Level Agreements ([SLAs](https://docs.google.com/spreadsheets/d/1Qcfve-nHlS0Udq31nZlfwBDjguhsJ8sxm0Q7RqfZM8o/edit#gid=0)) define three levels of production incidents: "Blocker", "Critical", and "Minor", and our agreed-to standards for incident response time per incident type. We collect metrics to determine how well our incident response times adhere to our SLAs.

## How we track metrics

We track metrics around "Blocker" and "Critical" type issues, and collect the following metrics per incident:
- time to issue addressed
- time to issue remediated
- time to users informed
- time to post-mortem notes available 

We detect production incidents either manually or via alerts from PagerDuty.  For incidents that go through PagerDuty, the incident "begins" when the PagerDuty alert happens.  Otherwise, the incident "begins" when a ticket is created on the PROD Jira board.  We collect subsequent timestamps as the production ticket and follow up tickets move in Jira, corresponding to the remediation actions taken, as detailed in our [SDLC](https://docs.google.com/document/d/1rLUMry-VAWsewEz2mOLfdzH-7UKxuIn35VlzZH90CcI/edit#).  We use timestamps in these tools to gather metrics:

|   | Metric start | Metric end |
| --- | --- | --- |
| time to issue addressed | PagerDuty alert if issue went through PD, else Jira bug creation time | Jira bug created |
| time to issue remediated | PagerDuty alert if issue went through PD, else Jira bug creation time | Jira bug marked as "Remediated" |
| time to users informed | PagerDuty alert if issue went through PD, else Jira bug creation time | Jira field "Users Informed" marked true |
| time to post-mortem complete | PagerDuty alert if issue went through PD, else Jira bug creation time | Post-mortem epic marked as "Postmortem Meeting Complete" |

## How we collect metrics

Metrics are collected by querying the Jira API for the two tickets associated with each incident: 1) the bug ticket for the actual incident and 2) the epic ticket to track the incident's post mortem. 

The bug ticket caputres the following information:
- incident start time (either via "Pagerduty incident start time" field or ticket creation time)
- remediation time (time ticket was moved to "Remediated")
- Incident priority (Blocker or Critical)
- user contacted time (via "Users Informed" field)

The epic ticket captures the following information:
- time the post-mortem was scheduled (time ticket moved to "Postmortem Scheduled")
- time the post-mortem was complete (time ticket moved to "Postmortem Complete")

Parsed metrics are sent to a BigQuery table called ["incident_metrics"](https://console.cloud.google.com/bigquery?project=terra-sla&p=terra-sla&d=sla&t=incident_metrics&page=table) in the `terra-sla` google project.  From here, metrics are exported to the adherence dashboard. 

### Usage

To load a set of metrics for a single incident:
```
./export_prod_jira.sh <epic ticket id>
# ex) ./export_prod_jira.sh PROD-365
```

## Adherence Dashboard

From the BigQuery metrics, adherence to our SLAs is tracked on [this dashboard](https://datastudio.google.com/u/0/reporting/1jYdIsy7oqok8jC-d0OcCODdFqYwJR3HV/page/7GlNB). 

Metrics are uploaded at the end of post-mortems via [a Jenkins job](https://fc-jenkins.dsp-techops.broadinstitute.org/job/upload-terra-incident-metrics/).  At the post-mortem we'll also reflect on our adherence and opportunities for improvement to achieve a goal 95% adherence.
