from dateutil.parser import *
import argparse
import requests
import sys
import datetime


def to_timestamp(time_str):
    if time_str:
        return parse(time_str)
    return None


def get_changelog_timestamp(changelog_list, changed_to):
    for i in changelog_list:
        if i.get('items')[0].get('toString') == changed_to:
            return i.get('created')


# Time diff with error handling for null case
def time_diff(start, end):
    if start and end:
        return start - end
    return None


class IncidentMetrics:
    """Class for the meterics of a production incident.

    Args:
        bug (dict): Jira API bug ticket
        epic (dict): Jira API epic ticket

    Attributes:
        metrics (dict): dictionary of metrics where each is represented as
           { key (str): metric }, where metric may be a boolean, int, or timestamp

    The metrics collected:
        - "id": (int) uuid of incident (Jira bug id)
        - "is_business_hours": (bool) if incident occurred during business hours (9am - 5pm)
        - "is_blocker": (bool) if the issue had priority "Blocker"
        - "time_to_issue_addressed": (timestamp) diff between issue start time and when bug ticket was opened
        - "time_to_user_contacted": (timestamp) diff between issue start time and when users were informed
        - "time_to_issue_remediated": (timestamp) diff between issue start time and when issue was remediated
        - "time_to_post_mortem_scheduled": (timestamp) diff between issue start time and when post-mortem scheduled
        - "time_to_post_mortem_complete": (timestamp) diff between issue start time and when post-mortem completed
    """
    def __init__(self, bug, epic):
        self.bug = bug
        self.epic = epic
        start_time = to_timestamp(self.bug.get('fields').get('customfield_10064'))

        self.metrics = {
            'id': bug.get('id'),
            'is_business_hours': self.get_is_business_hours(start_time),
            'is_blocker': self.get_is_blocker()
        }
        self.set_time_deltas(start_time)

    def set_time_deltas(self, start_time):
        bug_changelog = self.bug.get('changelog').get('histories')
        epic_changelog = epic.get('changelog').get('histories')

        self.metrics['time_to_issue_addressed'] = time_diff(
            start_time, to_timestamp(self.bug.get('fields').get('created')))
        self.metrics['time_to_issue_remediated'] = time_diff(start_time, to_timestamp(
            get_changelog_timestamp(bug_changelog, 'Remediated')))
        self.metrics['time_to_post_mortem_scheduled'] = time_diff(start_time, to_timestamp(
            get_changelog_timestamp(epic_changelog, 'Postmortem Scheduled')))
        self.metrics['time_to_post_mortem_complete'] = time_diff(start_time, to_timestamp(
            get_changelog_timestamp(epic_changelog, 'Postmortem Complete')))

        # TODO when field exists
        # self.metrics['time_to_user_contacted'] = self.start_time - to_timestamp()

    def get_is_business_hours(self, start_time):
        # where "business hours" are defined as 9am - 5pm
        return datetime.time(9, 0, 0) <= start_time.time() <= datetime.time(17, 0, 0)

    def get_is_blocker(self):
        return self.bug.get('fields').get('priority').get('name') == 'Blocker'


def get_metrics(args, jira_epic):
    """
    Creates an IncidentMetrics object from the Jira epic associated with the incident.

    Every incident has two Jira tickets associated with it: the Bug ticket which is filed by the
    on-call engineer after the incident begins, and the Epic ticket which is created after the incident
    is resolved.  The bug ticket should be linked to the epic.

    From the metadata attached to these two tickets fetched by the Jira API, all incident
    metrics can be calculated. 
    """
    bugs = [i for i in jira_epic.get('fields').get('issuelinks')
            if (i.get('outwardIssue').get('fields').get('issuetype').get('name') == 'Bug')]
    if len(bugs) > 1:
        sys.exit('Jira epic has more than one bug associated with it.')
    jira_bug = get_jira_issue(args.apiUser, args.apiToken, bugs[0].get('outwardIssue').get('key'))

    return IncidentMetrics(jira_bug, jira_epic)


def get_jira_issue(api_user, api_token, issue):
    """
    Calls the Jira API to get a particular issue.  Returns a dict of the issue metadata.
    """
    r = requests.get(
        'https://broadworkbench.atlassian.net/rest/api/3/issue/' + issue + '?expand=changelog',
        auth=(api_user, api_token))
    return r.json()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apiUser')
    parser.add_argument('--apiToken')
    parser.add_argument('--issue')

    args = parser.parse_args()

    # The epic moving to "post-mortem complete" is the entrypoint for collecting metrics, and marks
    # when incident remediation is "over."
    epic = get_jira_issue(args.apiUser, args.apiToken, args.issue)
    metrics = get_metrics(args, epic)
    # TODO: send metrics to bigquery

    print(metrics.metrics)

