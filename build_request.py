import os, re, time, requests
from urllib.parse import urlparse
from redminelib import Redmine

URL_REDMINE = 'https://mars.alpine.de/redmine/spf/'
KEY_REDMINE = 'b323dd5d4d24ffaca6c4206eedc04be2244224c8'
# Redmine Status
INIT = 0
OPEN = 1
BUILDING = 28
TESTING = 29
FINISH = 30
FAILED = 40
WAITING = 41

TOKEN_GITHUB = '6e71a8b20722fc51913d3263791c01489a97eacc'

PY_PRJ = os.getenv('ZUUL_COMMIT_PRJ')
PY_SHA = os.getenv('ZUUL_COMMIT_SHA')
PY_BRC = os.getenv('ZUUL_COMMIT_BRC')
PY_REF = os.getenv('ZUUL_COMMIT_REF')
PY_SNM = os.getenv('ZUUL_COMMIT_SNM')
PY_PRN = os.getenv('ZUUL_COMMIT_PRN')
PY_PUR = str(PY_PRJ) + '/pull/' + str(PY_PRN)

SUBJECT = 'Build Request from Github/Zuul:' + str(PY_SNM) + ' #' + str(PY_PRN)
DESCRIPTION = 'PROJECT:' + str(PY_PRJ) + '\n PULL_REQUEST:' + str(PY_PUR) + '\n SHA1:' + str(PY_SHA) + '\n BRANCH:' + str(PY_BRC) + '\n REFERENCE:' + str(PY_REF) + '\n'

pr_url_re = re.compile(
    '^/(?P<owner>.*?)/(?P<repos>.*?)/pull/(?P<id>.*?)$')

# Search Redmine Ticket is already available or not
def search_rm_ticket():
    print('=====Check Redmine Ticket=====')
    # Search for Previous issued Ticket
    redmine = Redmine(URL_REDMINE, key=KEY_REDMINE)
    issues = redmine.issue.filter(subject=SUBJECT, status_id = "*")
    
    # If there is no Ticket return num=0
    if len(issues) == 0:
        rm = 0
    else:    
        for issue in issues:
            # Store available Ticket id
            rm = issue.id

    return(rm)

# Create Redmine Ticket
def create_rm_ticket():
    print('=====Create Redmine Ticket=====')
    # Redmine Issue Create Setting
    redmine = Redmine(URL_REDMINE, key=KEY_REDMINE)
    issue = redmine.issue.new()
    issue.project_id = 15
    issue.subject = SUBJECT
    issue.tracker_id = 19
    issue.description = DESCRIPTION
    issue.status_id = OPEN 
    issue.save()

    # Output Response
    print('RedmineID:%d' % issue.id)
    print('subject:%s' % issue.subject)
    print('description:%s' % issue.description)

    COMMENT = 'RedmineID:' + str(issue.id) + '\n RedmineURL:' + str(URL_REDMINE) + 'issues/' + str(issue.id) + '\n subject:' + str(issue.subject) + '\n description:' + str(issue.description)

    return(issue.id, COMMENT)

# Update Redmine Ticket
def update_rm_ticket(rm_num):
    print('=====Update Redmine Ticket=====', rm_num)
    # Redmine Issue Create Setting
    redmine = Redmine(URL_REDMINE, key=KEY_REDMINE)
    issue = redmine.issue.update(rm_num,
        description = DESCRIPTION,
        status_id = OPEN,
        notes='Update Description')
    
    if issue == True:
        issue = redmine.issue.get(rm_num)
        # Output Response
        print('RedmineID:%d' % issue.id)
        print('subject:%s' % issue.subject)
        print('description:%s' % issue.description)
    
        COMMENT = 'RedmineID:' + str(issue.id) + '\n RedmineURL:' + str(URL_REDMINE) + 'issues/' + str(issue.id) + '\n subject:' + str(issue.subject) + '\n description:' + str(issue.description)
    else:
        print('########Ticket Update FAIL#########')

    return(issue.id, COMMENT)

# Check Redmine Ticket status
def check_rm_status(rm_id):
    print('=====Check Redmine Ticket Status=====')
    print(f' ID list : New={OPEN}, Building={BUILDING}, Testing={TESTING}, Waiting={WAITING}, Finished={FINISH}, Failed={FAILED}')
    status = OPEN
    last_status = INIT
    count, waiting_count = 0, 0
    
    # Status != Finish and 90min
    while status != FINISH and count < 90:
        redmine = Redmine(URL_REDMINE, key=KEY_REDMINE)
        issue = redmine.issue.get(rm_id)
        status = issue.status.id
        print(f'=====Check Status===== ID:[{status}], count:[{count + waiting_count}]')

        # Set initial status
        if last_status == INIT:
            last_status = status
        
        if status == FAILED:
            print('Build Failed')
            raise Exception
            
        # Clear count if status(build phase) changed
        if last_status != status:
            last_status = status
            count, waiting_count = 0, 0
            print('Build phase changed')

        time.sleep(60)
        count = count + 1

        if count == 90 and status == WAITING and not waiting_count:
            count, waiting_count = 60, 30
            print(f' waiting timeout 120 minutes. add count +30')
            
    if count == 90 and status != FINISH:
        print(f' Build Time Out [{count + waiting_count}min]')
        raise Exception

    print('Status[%d]' % status)

# Prepare Github communication Header information
def build_github_headers(server):
    token = TOKEN_GITHUB
    api_url = f"https://{server}/api/v3"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    return (api_url, headers)

# Post to Github
def post_request(server, path, json):
    (base_url, headers) = build_github_headers(server)
    url = f"{base_url}{path}"
    return requests.post(url, json=json, headers=headers)

# Prepare Github response
def split_pr(pr_url):
    url_info = urlparse(pr_url)
    match = pr_url_re.search(url_info.path)
    server = url_info.netloc
    owner = match.group('owner')
    repos = match.group('repos')
    pr_id = match.group('id')
    return (server, owner, repos, pr_id)

# Send message to Github
def post_comment_to_pr(pr_url, COMMENT):
    (server, owner, repos, pr_id) = split_pr(pr_url)
    url = f"/repos/{owner}/{repos}/issues/{pr_id}/comments"
    response = post_request(server, url, {"body": COMMENT})
    return response

# main
if __name__ == '__main__':
    # Check Redmine Ticket is avairable or not
    rmnum = search_rm_ticket()
    # Switch Ticket is available or not
    if rmnum != 0:
        print("Update Ticket")
        # update Redmine Ticket
        (rm_id, COMMENT) = update_rm_ticket(rmnum)
    else:
        print("Create Ticket")
        # Create Redmine Ticket
        (rm_id, COMMENT) = create_rm_ticket()
    # Send Response to PU ticket
    res = post_comment_to_pr(PY_PUR, COMMENT)
    print(res)
    # Check Redmine Ticket Status
    check_rm_status(rm_id)