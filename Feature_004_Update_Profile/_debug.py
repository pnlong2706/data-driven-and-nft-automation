import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1366,900')
opts.add_argument('--disable-gpu')
d = webdriver.Chrome(options=opts)

# Login
d.get('https://school.moodledemo.net/login/index.php')
d.delete_all_cookies()
d.get('https://school.moodledemo.net/login/index.php')
WebDriverWait(d, 15).until(EC.presence_of_element_located((By.ID, 'username')))
d.find_element(By.ID, 'username').send_keys('student')
d.find_element(By.ID, 'password').send_keys('moodle26')
d.find_element(By.ID, 'loginbtn').click()
WebDriverWait(d, 15).until(lambda x: '/my/' in x.current_url)

# Cancel pending email
d.get('https://school.moodledemo.net/user/edit.php')
WebDriverWait(d, 15).until(EC.presence_of_element_located((By.ID, 'id_firstname')))
links = d.find_elements(By.XPATH, "//a[contains(@href,'cancelemailchange')]")
if links:
    print("Cancelling pending email...")
    links[0].click()
    time.sleep(2)
    d.get('https://school.moodledemo.net/user/edit.php')
    WebDriverWait(d, 15).until(EC.presence_of_element_located((By.ID, 'id_firstname')))

print('Original firstname:', d.find_element(By.ID, 'id_firstname').get_attribute('value'))

# Simulate TC-004-002: clear firstname and submit with novalidate
el = d.find_element(By.ID, 'id_firstname')
el.clear()
d.execute_script(
    "var f=document.getElementById('id_submitbutton').closest('form');"
    "f.setAttribute('novalidate','true');"
)
d.find_element(By.ID, 'id_submitbutton').click()
time.sleep(2)
print('After TC-002 submit, URL:', d.current_url)
errors = d.find_elements(By.XPATH, "//span[contains(@class,'error')]")
print('Page has error elements:', len(errors))
for e in errors:
    if e.text.strip():
        print('  Error:', e.text.strip())

# Now simulate TC-004-003: navigate fresh, type with spaces, submit
print('\n--- TC-004-003 ---')
d.get('https://school.moodledemo.net/user/edit.php')
WebDriverWait(d, 15).until(EC.presence_of_element_located((By.ID, 'id_firstname')))
print('Firstname before typing:', repr(d.find_element(By.ID, 'id_firstname').get_attribute('value')))

el = d.find_element(By.ID, 'id_firstname')
el.clear()
el.send_keys('   Study Testing   ')
typed_val = d.find_element(By.ID, 'id_firstname').get_attribute('value')
print('Firstname after typing:', repr(typed_val))

d.execute_script(
    "var f=document.getElementById('id_submitbutton').closest('form');"
    "f.setAttribute('novalidate','true');"
)
d.find_element(By.ID, 'id_submitbutton').click()
time.sleep(3)
print('After submit URL:', d.current_url)

# Check if we got errors or success
errors2 = d.find_elements(By.XPATH, "//span[contains(@class,'error')]")
print('Errors after submit:', len(errors2))
for e in errors2:
    if e.text.strip():
        print('  Error:', e.text.strip())

# Re-open and check saved value
d.get('https://school.moodledemo.net/user/edit.php')
WebDriverWait(d, 15).until(EC.presence_of_element_located((By.ID, 'id_firstname')))
saved = d.find_element(By.ID, 'id_firstname').get_attribute('value')
print('Saved firstname:', repr(saved))

d.quit()
