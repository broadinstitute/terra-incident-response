# Terra Incident Response tracking

Terra's Service Level Agreements ([SLAs](https://docs.google.com/spreadsheets/d/1Qcfve-nHlS0Udq31nZlfwBDjguhsJ8sxm0Q7RqfZM8o/edit#gid=0)) define three levels of production incidents: "Blocker", "Critical", and "Minor", and our agreed-to standards for incident response time per incident type. We collect metrics to determine how well our incident response times adhere to our SLAs.

## How we track metrics

We track metrics around "Blocker" and "Critical" type issues, and collect the following metrics per incident:
- time to issue addressed
- time to issue remediated
- time to users informed
- time to post-mortem notes availible 

We detect production incidents either manually or via alerts from PagerDuty, and track them as tickets in Jira.  The issue type (Blocker or Critical) corresponds to the ticket priority.  We can collect timestamps from these tools to measure the above metrics.

|   | Metric start | Metric end |
| --- | --- | --- | --- | --- |
| time to issue addressed | PagerDuty alert if issue went through PD, else Jira bug creation time | Jira bug created |
| time to issue remediated | PagerDuty alert if issue went through PD, else Jira bug creation time | Jira bug marked as "Remediated" |
| time to users informed | PagerDuty alert if issue went through PD, else Jira bug creation time | Jira field "Users Informed" marked true |
| time to post-mortem complete | PagerDuty alert if issue went through PD, else Jira bug creation time | Post-mortem epic marked as "Postmortem Meeting Complete" |

Incident management is further detailed in our [SDLC](https://docs.google.com/document/d/1rLUMry-VAWsewEz2mOLfdzH-7UKxuIn35VlzZH90CcI/edit#). 

## How we collect metrics