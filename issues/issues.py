import re
import logging
from jira.client import JIRA 
from atlassian_doc_builder import ADFDoc
from jira.resources import Issue

# Issues - Python class to manipulate JIRA issues using the JIRA Python SDK
class Issues:

    # Issues Constructor
    # jira_credentials: JIRA credentials object
    # project_key: Project key string
    # email_domain: Email domain string
    # default_issue_labels: Default issue labels list
    # logger: Logger object
    #
    # Returns: Issues object
    # Raises: None
    def __init__(self, logger: logging.Logger, jira_credentials: JIRA, project_key: str, project_id: int, email_domain: str, default_issue_labels: list = []):
        self.jira = jira_credentials
        self.project_key = project_key
        self.project_id = project_id
        self.email_domain = email_domain
        self.default_issue_labels = default_issue_labels
        self.logger = logger
    
    # Check if JIRA issue already exists, returns bool and issue_key if key exists
    def __does_issue_exist(self, issue_summary: str) -> tuple[bool, str]:

        # Search for issues in this project where the given summary matches exactly and the status is not Done to avoid older issues being updated with newer findings. Newer findings require newer tickets in that case.
        issues = self.jira.search_issues(
            'project = ' + self.project_key + ' AND status = "To Do" AND summary ~ "\\"' + issue_summary + '\\""'
        )

        self.logger.debug("Search Issue results - " + str(issues))

        if len(issues) > 0:
            self.logger.info("Issue already exists - " + str(issues))
            return True, issues[0].key
        else:
            self.logger.info("Issue does not exist - " + str(issues))
            return False, ''
    
    # Create a new JIRA issue
    def __create_issue(self, issue_summary: str, issue_desc: ADFDoc, issue_type: str) -> Issue:        

        # Create an issue
        new_issue = self.jira.create_issue(
            fields={
                'project': self.project_id,
                'summary': issue_summary,
                'description': str(issue_desc.validate()) if isinstance(issue_desc, ADFDoc) else str(issue_desc),
                'issuetype': {'name': issue_type}
            }
        )
        self.logger.info("New Issue created: " + str(new_issue))
        self.logger.info("New Issue type: " + str(type(new_issue)))
        return new_issue

    # Get an JIRA issue
    def __get_issue(self, issue_id: str) -> Issue:

        issue = self.jira.issue(issue_id)
        self.logger.debug("Get Issue: " + str(issue.fields.summary) + " - " + str(issue.fields.description))
        return issue

    # Update an JIRA issue
    def __update_issue(self, issue_id: str, issue_summary: str, issue_desc: ADFDoc) -> Issue:

        self.logger.debug("Updating Issue ID: " + issue_id)

        # Change the issue's summary and description.
        self.jira.issue(issue_id).update(
            fields={
                'summary': issue_summary,
                'description': str(issue_desc.validate()) if isinstance(issue_desc, ADFDoc) else str(issue_desc)
            },
            notify=True
        )

        updated_issue = self.jira.issue(issue_id)
        self.logger.debug("Issue Updated: " + str(updated_issue.fields.summary) + " - " + str(updated_issue.fields.description))
        return updated_issue
    
    def upsert_jira_issue(self, issue_summary: str, issue_desc: ADFDoc, issue_type: str = "Task") -> Issue:

        # Check if issue already exists. If it does, then don't create a new issue. If it doesn't, then create a new issue
        # Returns bool and issue_key if key exists. Returns bool and empty string if key doesn't exist.
        key_info = self.__does_issue_exist(issue_summary = issue_summary)

        if key_info[0]:

            issue = self.__get_issue(issue_id = key_info[1])

            # Compare hashes of server version (issue.fields.description) and local version (issue_desc)
            if isinstance(issue_desc, ADFDoc):
                issue_desc = str(issue_desc.validate())

            if hash(issue.fields.description) != hash(issue_desc):
                self.logger.debug("Issue Description has changed. Updating Issue.")

                return self.__update_issue(
                    issue_id = key_info[1],
                    issue_summary = issue_summary,
                    issue_desc = issue_desc,
                )
            else:
                self.logger.debug("Issue Description has not changed. Issue does not need an update.")
            return issue
        else:
            # Create an Issue with the data object
            new_issue = self.__create_issue(
                issue_summary = issue_summary,
                issue_desc = issue_desc,
                issue_type = issue_type
            )

            if self.default_issue_labels:
                self.logger.debug("Tagging mandatory labels onto Issue.")
                self.__tag_mandatory_labels_onto_issue(issue_id = new_issue)
            else:
                self.logger.debug("No mandatory labels to tag onto Issue.")

            return new_issue

    # Tag mandatory labels onto a JIRA issue
    def __tag_mandatory_labels_onto_issue(self, issue_id: str) -> Issue:

        # Get an issue.
        issue = self.jira.issue(issue_id)

        # Modify the List of existing labels. The new label is unicode with no spaces
        for label in self.default_issue_labels:
            issue.fields.labels.append(label)

        # Change the issue without sending updates
        issue.update(notify=False, fields={"labels": issue.fields.labels})

        return issue 
    
    # Get all comments on an issue
    def __get_comments_on_issue(self, issue_id: str) -> Issue:

        # Get an issue.
        issue = self.jira.issue(issue_id)

        # Find all comments made by your Organization on this issue.
        org_comments = [
            comment
            for comment in issue.fields.comment.comments
            if re.search(self.email_domain, comment.author.emailAddress)
        ]

        self.logger.info("Issue Comments - " + str(org_comments))

        return issue

    # Add comments on an issue
    def __put_comments_on_issue(self, issue_id: str) -> Issue:

        # Get an issue.
        issue = self.jira.issue(issue_id)

        # Add a comment to the issue.
        self.jira.add_comment(issue, "Comment text. Added by Python using JIRA APIs.")

        return issue

    # # Delete an issue
    # def __delete_issue(self, issue_id: str):

    #     # Get an issue.
    #     issue = self.jira.issue(issue_id)
        
    #     # Send the issue away for good.
    #     issue.delete()

    # Link two issues
    def __link_issue(self, issue_id1: str, issue_id2: str):

        # Linking a remote jira issue (needs applinks to be configured to work)
        issue1 = self.jira.issue(issue_id1)
        issue2 = self.jira.issue(issue_id2)  # could also be another instance
        self.jira.add_remote_link(issue1.id, issue2)