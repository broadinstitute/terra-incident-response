from dateutil.parser import *
import dateutil
import argparse
import requests
import sys
import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
import json
from google.api_core.exceptions import BadRequest



def to_timestamp(time_str):
    if time_str:
        # Note, the "default" here fills in blank fields; we use this to fill in timezone info for the naive timestamps
        return parse(time_str, default=default_time()).replace(microsecond=0) 
    return None

def nyc_tz_string():
    # Gets the offset from NYC (eastern) time
    # Usually returns "-5" ("-4" during daylight savings)
    time_diff = dateutil.tz.gettz('America/New York').utcoffset(parse('00:00'))
    time_diff_hrs = int(time_diff.days*24+round(time_diff.seconds/3600.0))
    tz_string=str(time_diff_hrs)
    if time_diff_hrs >=0:
        tz_string = '+' + tz_string
    return tz_string

def default_time():
    # Returns a timestamp with the timezone offset from NYC (eastern time)
    return parse('00:00 ' + nyc_tz_string())

def get_changelog_timestamp(changelog_list, changed_to, changed_from=[], field=''):
    for i in changelog_list:
        if field:
            if i.get('items')[0].get('field') != field:
                continue

        if i.get('items')[0].get('toString') == changed_to:
            if changed_from:
                if i.get('items')[0].get('fromString') in changed_from:
                    return i.get('created')
                else:
                    continue
            else:
                return i.get('created')


# Time diff with error handling for null case
def time_diff(start, end):
    if start and end:
        return datetime.datetime.min + (end - start)
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
        - "issue_id": (str) Jira epic ticket #
        - "is_business_hours": (bool) if incident occurred during business hours (9am - 4pm)
        - "is_blocker": (bool) if the issue had priority "Blocker"
        - "incident_timestamp": (timestamp) start time of incident
        - "issue_addressed": (timestamp) when bug ticket was opened or page acknowledged
        - "user_contacted": (timestamp) when users were informed
        - "issue_remediated": (timestamp) when issue was remediated
        - "mortem_scheduled": (timestamp) when post-mortem was scheduled
        - "postmortem_complete": (timestamp) when post-mortem was completed
    """
    def __init__(self, bug, epic, timestamps):
        self.bug = bug
        self.epic = epic
        start_time = self.get_start_time()
        print('creating metrics for incident beginning at {}'.format(start_time))
        
        self.metrics = {
            'id': bug.get('id'),
            'is_business_hours': self.get_is_business_hours(start_time),
            'is_blocker': self.get_is_blocker(),
            'incident_timestamp': start_time,
            'issue_id': epic.get('key')
        }
        self.set_time_deltas(start_time, timestamps)

    def set_time_deltas(self, start_time, timestamps):
        bug_changelog = self.bug.get('changelog').get('histories')
        epic_changelog = epic.get('changelog').get('histories')

        self.metrics['issue_addressed'] = to_timestamp(
            timestamps.get('issue_addressed') or 
            self.bug.get('fields').get('created')
        )
        self.metrics['issue_remediated'] = to_timestamp(
            timestamps.get('issue_remediated') or 
            get_changelog_timestamp(bug_changelog, 'Remediated', changed_from=['To Do', 'In Progress', 'On Dev'])
        )
        self.metrics['mortem_scheduled'] = to_timestamp(
            get_changelog_timestamp(epic_changelog, 'incident review Scheduled', changed_from=['To Do', 'Needs incident review'])
        )
        self.metrics['postmortem_complete'] = to_timestamp(
            timestamps.get('postmortem_complete') or
            get_changelog_timestamp(epic_changelog, 'incident review Meeting Complete', changed_from=['incident review Scheduled', 'Needs incident review'])
        )
        self.metrics['user_contacted'] = to_timestamp(
            timestamps.get('user_contacted') or
            get_changelog_timestamp(bug_changelog, 'Yes', changed_from='No', field='Users Informed')
        )

    def get_is_business_hours(self, start_time):
        # where "business hours" are defined as 9am - 4pm
        return datetime.time(9, 0, 0) <= start_time.time() <= datetime.time(16, 0, 0)

    def get_is_blocker(self):
        return self.bug.get('fields').get('priority').get('name') == 'Blocker'

    def get_start_time(self):
        start_time = to_timestamp(self.bug.get('fields').get('customfield_10064'))
        if not start_time:
            start_time = to_timestamp(self.bug.get('fields').get('created'))
        return start_time


def get_metrics(args, jira_epic):
    """
    Creates an IncidentMetrics object from the Jira epic associated with the incident.

    Every incident has two Jira tickets associated with it: the Bug ticket which is filed by the
    on-call engineer after the incident begins, and the Epic ticket which is created after the incident
    is resolved.  The bug ticket should be linked to the epic.

    From the metadata attached to these two tickets fetched by the Jira API, all incident
    metrics can be calculated.
    """
    links = jira_epic.get('fields').get('issuelinks')
    bugs = [i for i in links
            if (i.get('outwardIssue', {}).get('fields', {}).get('issuetype', {}).get('name', {}) == 'Bug') or
            (i.get('inwardIssue', {}).get('fields', {}).get('issuetype', {}).get('name', {}) == 'Bug')]

    if len(bugs) < 1:
        sys.exit('Jira epic has incorrect number of Remediated bugs linked to it.  Has {} bugs'.format(len(bugs)))
    bug_id = bugs[0].get('outwardIssue', {}).get('key') or bugs[0].get('inwardIssue', {}).get('key')
    jira_bug = get_jira_issue(args.apiUser, args.apiToken, bug_id)
    timestamps = get_timestamp_dict(vars(args))
    with open('issue.json', 'w') as f:
        json.dump(jira_bug, f)

    return IncidentMetrics(jira_bug, jira_epic, timestamps)

def get_timestamp_dict(timestamp_dict):
    def remove_time(s):
        # Reformats "time_issue_addressed", an externally-facing key, to "issue_addressed", an internally-facing key.
        return s.split('time_')[1]
    timestamp_dict_keys = ['time_issue_addressed', 'time_issue_remediated', 'time_user_contacted', 'time_postmortem_complete']
    timestamp_dict = {remove_time(key):timestamp_dict.get(key) for key in timestamp_dict_keys}
    return timestamp_dict

def get_jira_issue(api_user, api_token, issue):
    """
    Calls the Jira API to get a particular issue.  Returns a dict of the issue metadata.
    """
    r = requests.get(
        'https://broadworkbench.atlassian.net/rest/api/3/issue/' + issue + '?expand=changelog',
        auth=(api_user, api_token))
    return r.json()


def get_bigquery_meta(svc_acct_path):
    credentials = service_account.Credentials.from_service_account_file(
        svc_acct_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    client = bigquery.Client(credentials=credentials, project='terra-sla')
    dataset_id = 'sla'
    table_id = 'incident_metrics'
    dataset_ref = client.dataset(dataset_id)
    table_ref = dataset_ref.table(table_id)

    return client, dataset_id, table_id, table_ref


def send_metrics_to_bigquery(metrics, svc_acct_path, sql_action):
    client, dataset_id, table_id, table_ref = get_bigquery_meta(svc_acct_path)

    job_config = bigquery.LoadJobConfig()
    job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
    job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    # disabling this allows nulls to be uploaded correctly rather than interpreted as strings
    # job_config.autodetect = True

    # table rows must be written to a file; currently the only way I know how to upload from a map
    jsonable_metrics = {k: (v.__str__() if (isinstance(v, datetime.time) or isinstance(v, datetime.datetime)) else v)
                        for k, v in metrics.iteritems()}

    if sql_action == 'update':
        print('WARNING! Deleting existing row from table.')
        query = 'DELETE FROM {}.{} WHERE issue_id="{}"'.format(dataset_id, table_id, metrics['issue_id'])
        try:
            job = client.query(query)
        except BadRequest as ex:
            print(ex)
        job.result()
        print('Deleted one row from {}:{}.').format(dataset_id, table_id)

    with open('metrics.json', 'w') as write_file:
        json.dump(jsonable_metrics, write_file)
    with open('metrics.json', 'rb') as readfile:
        try:
            job = client.load_table_from_file(readfile, table_ref, job_config=job_config)
        except BadRequest as ex:
            print(ex)

    job.result()
    print('Loaded {} rows into {}:{}.'.format(job.output_rows, dataset_id, table_id))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apiUser')
    parser.add_argument('--apiToken')
    parser.add_argument('--issue')
    parser.add_argument('--bigquerySvcAcct')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--time_issue_addressed')
    parser.add_argument('--time_issue_remediated')
    parser.add_argument('--time_user_contacted')
    parser.add_argument('--time_postmortem_complete')
    parser.add_argument('--sql_action', 
        default = 'append', 
        choices = ['append', 'update'], 
        help = '"append" to append new row, "update" to overwrite existing row'
    )

    args = parser.parse_args()
    
    # The epic moving to "post-mortem complete" is the entrypoint for collecting metrics, and marks
    # when incident remediation is "over."
    epic = get_jira_issue(args.apiUser, args.apiToken, args.issue)
    metrics = get_metrics(args, epic)
    print metrics.metrics

    if args.test:
        print 'This is a test.  Not sending any data to Big Query.'
    else:
        send_metrics_to_bigquery(metrics.metrics, args.bigquerySvcAcct, args.sql_action)

