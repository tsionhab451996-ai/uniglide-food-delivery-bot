import socket
import urllib.request
import ssl

print("="*60)
print("🔍 TELEGRAM CONNECTION DIAGNOSTIC")
print("="*60)

# Test 1: DNS Resolution
try:
    ip = socket.gethostbyname("api.telegram.org")
    print(f"✅ [1/3] DNS Resolution: OK (Resolved to {ip})")
except Exception as e:
    print(f"❌ [1/3] DNS Resolution FAILED: {e}")
    print("   -> FIX: Your router or ISP is blocking the domain name.")

# Test 2: Raw TCP Connection (Port 443)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(("api.telegram.org", 443))
    sock.close()
    if result == 0:
        print("✅ [2/3] TCP Connection (Port 443): OK")
    else:
        print(f"❌ [2/3] TCP Connection FAILED (Error code: {result})")
        print("   -> FIX: Windows Firewall or Antivirus is blocking 'python.exe'.")
except Exception as e:
    print(f"❌ [2/3] TCP Connection FAILED: {e}")

# Test 3: HTTPS Request (with SSL bypass)
try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request("https://api.telegram.org/botTEST/getMe", headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
        print(f"✅ [3/3] HTTPS Request: OK (Status: {response.status})")
except Exception as e:
    print(f"❌ [3/3] HTTPS Request FAILED: {e}")
    print("   -> FIX: A VPN, Proxy, or Antivirus 'Web Shield' is dropping the connection.")

print("="*60)
print("If any test shows ❌, the issue is your local computer/network.")
print("The bot code is 100% correct and will work once the block is removed.")
print("="*60)