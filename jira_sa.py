from configparser import ConfigParser
from datetime import datetime
from enum import Enum
from jira import JIRA
import matplotlib.pyplot as plt
import requests


class TestCoverage(Enum):
    '''the name must be the same with the lable of jira issues'''
    Covered_by_Junit = 'Junit'
    Covered_by_Tuj = 'Tuj'
    Covered_by_manualCases = 'ManualCase'
    No_Case_Needed = 'NoCaseNeeded'
    No_Label = 'NoLabel'  # means don't have any of above labels


class JiraConfig(object):
    '''the configuration of jira: server address, username, password etc.'''
    def __init__(self, conf_file):
        cfg = ConfigParser()
        cfg.read(conf_file)
        self.__server = cfg.get('jira', 'server')
        self.__project_name = cfg.get('jira', 'project_name')
        self.__board_id = cfg.get('sprint', 'board_id')
        self.__sprint_id = cfg.get('sprint', 'sprint_id')
        self.__username = cfg.get('login', 'username')
        self.__password = cfg.get('login', 'password')

    @property
    def server(self):
        return self.__server

    @property
    def project_name(self):
        return self.__project_name

    @property
    def board_id(self):
        return self.__board_id

    @property
    def sprint_id(self):
        return self.__sprint_id

    @property
    def username(self):
        return self.__username

    @property
    def password(self):
        return self.__password


class JiraTestCoverage(object):
    '''store the result of jira test coverage'''
    def __init__(self):
        self.__sprint_id = '0'
        self.__sprint_name = 'no name'
        self.__start_date = None
        self.__end_date = None
        self.__issue_keys = set()  # all issue keys belong to the sprint
        self.__test_coverage_issues = {}  # store the test coverage of the sprint {key=label, value=number of issues}

    @property
    def sprint_id(self):
        return self.__sprint_id

    @sprint_id.setter
    def sprint_id(self, value):
        self.__sprint_id = value

    @property
    def sprint_name(self):
        return self.__sprint_name

    @sprint_name.setter
    def sprint_name(self, value):
        self.__sprint_name = value

    @property
    def start_date(self):
        return self.__start_date

    @start_date.setter
    def start_date(self, value):
        self.__start_date = value

    @property
    def end_date(self):
        return self.__end_date

    @end_date.setter
    def end_date(self, value):
        self.__end_date = value

    @property
    def issue_keys(self):
        return self.__issue_keys

    @property
    def test_coverage_issues(self):
        return self.__test_coverage_issues


def get_sprint_time_range(username, password, sprint_id):
    '''get the start and end date of the sprint'''
    url = f'https://jira.talendforge.org/rest/agile/1.0/sprint/{sprint_id}'
    response = requests.get(url, auth=(username, password))
    json = response.json()
    return get_date(*('startDate', 'endDate'), **json)


def get_date(*keys, **datas):
    '''get the datetime objects'''
    return tuple([datetime.strptime(datas[key][:10], '%Y-%m-%d') for key in keys])


def jira_sa(jira_config):
    '''analyse the test coverage of sprint, return JiraTestCoverage'''
    jira_test_coverage = JiraTestCoverage()
    jira_obj = JIRA(basic_auth=(jira_config.username, jira_config.password), server=jira_config.server)
    cur_sprint = jira_obj.sprint(jira_config.sprint_id)

    if cur_sprint:
        print(f'name=[{cur_sprint.name}] id=[{cur_sprint.id}]')
        sprint_start, sprint_end = get_sprint_time_range(jira_config.username, jira_config.password, cur_sprint.id)
        jira_test_coverage.sprint_id = cur_sprint.id
        jira_test_coverage.sprint_name = cur_sprint.name
        jira_test_coverage.start_date = sprint_start
        jira_test_coverage.end_date = sprint_end
        print(f'sprint_start: {sprint_start}; sprint_end: {sprint_end}')
        print(f'Querying all issues in current sprint....')
        issues = jira_obj.search_issues(f'Sprint={cur_sprint.id} and project = "{jira_config.project_name}" and type in ("New Feature", "Work Item", Bug)', maxResults=200)
        print(f'Total issues: {len(issues)}')
        for issue in issues:
            jira_test_coverage.issue_keys.add(issue.key)
            covered = False
            for label in issue.fields().labels:
                if label in TestCoverage.__members__.keys():
                    covered = True
                    if label in jira_test_coverage.test_coverage_issues.keys():
                        jira_test_coverage.test_coverage_issues[label].add(issue.key)
                    else:
                        jira_test_coverage.test_coverage_issues[label] = {issue.key}
            if not covered:
                if TestCoverage.No_Label.name in jira_test_coverage.test_coverage_issues.keys():
                    jira_test_coverage.test_coverage_issues[TestCoverage.No_Label.name].add(issue.key)
                else:
                    jira_test_coverage.test_coverage_issues[TestCoverage.No_Label.name] = {issue.key}

    return jira_test_coverage

def jira_viz(jira_test_coverage):
    '''generate the charts according to the input JiraTestCoverage object'''
    # make figure and assign axis objects
    fig = plt.figure(figsize=(9, 5.0625))
    ax1 = fig.add_subplot(121)
    fig.subplots_adjust(wspace=0)

    # pie chart parameters
    ratios = []
    labels = []

    total_issues_count = len(jira_test_coverage.issue_keys)
    if total_issues_count > 0:
        no_case_needed_issues = jira_test_coverage.test_coverage_issues.get(TestCoverage.No_Case_Needed.name, set())
        junit_issues = jira_test_coverage.test_coverage_issues.get(TestCoverage.Covered_by_Junit.name, set())
        tuj_issues = jira_test_coverage.test_coverage_issues.get(TestCoverage.Covered_by_Tuj.name, set())
        manual_case_issues = jira_test_coverage.test_coverage_issues.get(TestCoverage.Covered_by_manualCases.name, set())
        no_label_issues = jira_test_coverage.test_coverage_issues.get(TestCoverage.No_Label.name, set())

        junit_issues_only = junit_issues - tuj_issues - manual_case_issues
        tuj_issues_only = tuj_issues - junit_issues - manual_case_issues
        manual_case_issues_only = manual_case_issues - junit_issues - tuj_issues
        junit_tuj_issues_only = junit_issues & tuj_issues - manual_case_issues
        junit_manual_case_issues_only = junit_issues & manual_case_issues - tuj_issues
        tuj_manual_case_issues_only = tuj_issues & manual_case_issues - junit_issues
        junit_tuj_manual_case_issues = junit_issues & tuj_issues & manual_case_issues

        if len(no_label_issues)>0:
            ratios.append(len(no_label_issues)/total_issues_count)
            labels.append(f'{TestCoverage.No_Label.value}({len(no_label_issues)})')
        if len(no_case_needed_issues)>0:
            ratios.append(len(no_case_needed_issues)/total_issues_count)
            labels.append(f'{TestCoverage.No_Case_Needed.value}({len(no_case_needed_issues)})')
        if len(junit_issues_only)>0:
            ratios.append(len(junit_issues_only)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_Junit.value}({len(junit_issues_only)})')
        if len(tuj_issues_only)>0:
            ratios.append(len(tuj_issues_only)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_Tuj.value}({len(tuj_issues_only)})')
        if len(manual_case_issues_only)>0:
            ratios.append(len(manual_case_issues_only)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_manualCases.value}({len(manual_case_issues_only)})')
        if len(junit_tuj_issues_only)>0:
            ratios.append(len(junit_tuj_issues_only)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_Junit.value}+{TestCoverage.Covered_by_Tuj.value}({len(junit_tuj_issues_only)})')
        if len(junit_manual_case_issues_only)>0:
            ratios.append(len(junit_manual_case_issues_only)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_Junit.value}+{TestCoverage.Covered_by_manualCases.value}({len(junit_manual_case_issues_only)})')
        if len(tuj_manual_case_issues_only)>0:
            ratios.append(len(tuj_manual_case_issues_only)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_Tuj.value}+{TestCoverage.Covered_by_manualCases.value}({len(tuj_manual_case_issues_only)})')
        if len(junit_tuj_manual_case_issues)>0:
            ratios.append(len(junit_tuj_manual_case_issues)/total_issues_count)
            labels.append(f'{TestCoverage.Covered_by_Junit.value}+{TestCoverage.Covered_by_Tuj.value}+{TestCoverage.Covered_by_manualCases.value}({len(junit_tuj_manual_case_issues)})')

    explode = []
    for i in range(0, len(labels)):
        if i < len(labels) - 1:
            explode.append(0)
        else:
            explode.append(0.1)

    # rotate so that first wedge is split by the x-axis
    angle = -180 * ratios[0]
    ax1.pie(ratios, autopct='%1.2f%%', startangle=angle,
            labels=labels, explode=explode)
    ax1.set_title(f'{jira_test_coverage.sprint_name}\n{jira_test_coverage.start_date.strftime("%Y-%m-%d")} ~ {jira_test_coverage.end_date.strftime("%Y-%m-%d")}\nTotal Jira Issue: {len(jira_test_coverage.issue_keys)}', fontsize=12)

    # show the charts
    plt.show()


if __name__ == "__main__":
    jira_viz(jira_sa(JiraConfig('jira.conf')))