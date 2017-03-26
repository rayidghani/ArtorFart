import subprocess
container_id = 'e980159059f9'

def get_score(image_url):
    classify_cmd = "'/latteart/label_web_image.sh " + str(image_url) + "'"
    cmd = "docker exec " + container_id + " sh -c " + classify_cmd 
    p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
    out,err = p.communicate()
    return out

def get_biz_score(bizid):
    classify_cmd = "'/latteart/get_rating.sh " + str(bizid) + "'"
    cmd = "docker exec " + container_id + " sh -c " + classify_cmd
    p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
    out,err = p.communicate()
    return out

def get_biz_scores_from_location(location):
    classify_cmd = "'python /latteart/get_business_ranking.py " + str(location) + "'"
    cmd = "docker exec " + container_id + " sh -c " + classify_cmd
    p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
    out,err = p.communicate()
    return out
