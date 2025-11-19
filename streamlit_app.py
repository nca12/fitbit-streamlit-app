import streamlit as st 
import requests 
import os 
import hashlib 
import base64 
import urllib.parse 
 

# --- PAGE HEADER STYLING ---
st.markdown(
    """
    <style>
        .center-text {
            text-align: center;
        }
        .title-beige {
            color: #e4d7b7; /* beige */
            font-size: 60px;
            font-weight: 800;
            text-align: center;
            padding-bottom: 10px;
        }
        .subheader {
            text-align: center;
            font-size: 34px;
            font-weight: 600;
            padding-bottom: 20px;
        }
        .normal-text {
            text-align: center;
            font-size: 22px;
            line-height: 1.5;
            max-width: 900px;
            margin: auto;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- PAGE CONTENT ---
st.markdown('<div class="title-beige">Welcome to the Study!</div>', unsafe_allow_html=True)

st.markdown('<div class="subheader">Fitbit Authorization Page</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="normal-text">
        This secure page allows you to connect your Fitbit account using OAuth2 with PKCE.
        Once authenticated, the app will fetch your profile and provide access tokens for testing.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="subheader" style="margin-top: 40px;">To get started, connect your Fitbit account below.</div>', unsafe_allow_html=True)


# ============================================================ 
#                REQUIRED CONFIGURATION 
# ============================================================ 
CLIENT_ID = st.secrets["FITBIT_CLIENT_ID"]        # from .streamlit/secrets.toml 
REDIRECT_URI = "https://fitbit-verification-page-hsr.streamlit.app"    
 
SCOPES = (
    "activity heartrate location nutrition profile settings sleep social weight "
    "respiratory_rate temperature oxygen_saturation cardio_fitness "
    "electrocardiogram irregular_rhythm_notifications"
)

 
 
# ============================================================ 
#                PKCE GENERATION HELPERS 
# ============================================================ 
def generate_code_verifier(): 
    """Generate a 43–128 character URL-safe string.""" 
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8") 
    return verifier.rstrip("=") 
 
def generate_code_challenge(verifier: str): 
    """SHA256 + Base64URL → code challenge""" 
    sha256 = hashlib.sha256(verifier.encode("utf-8")).digest() 
    challenge = base64.urlsafe_b64encode(sha256).decode("utf-8") 
    return challenge.rstrip("=") 
 
 
# ============================================================ 
#                   STREAMLIT APP UI 
# ============================================================ 
#st.title("Fitbit OAuth2 PKCE Login Demo") 
 
params = st.experimental_get_query_params() 
auth_code = params.get("code", [None])[0] 
 
# Initialize PKCE in session state 
if "code_verifier" not in st.session_state: 
    st.session_state["code_verifier"] = generate_code_verifier() 
    st.session_state["code_challenge"] = generate_code_challenge(
        st.session_state["code_verifier"]
    ) 
 
 
# ============================================================ 
#                STEP 1 — Show Fitbit Login Link 
# ============================================================ 
if not auth_code: 
    auth_url = ( 
        "https://www.fitbit.com/oauth2/authorize?" 
        f"response_type=code&" 
        f"client_id={CLIENT_ID}&" 
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&" 
        f"scope={urllib.parse.quote(SCOPES)}&" 
        f"code_challenge={st.session_state['code_challenge']}&" 
        "code_challenge_method=S256" 
    ) 
 
    st.markdown("### Connect Your Fitbit Account") 
    st.markdown(f"[Click here to authorize Fitbit]({auth_url})", unsafe_allow_html=True) 
    st.stop() 
 
 
# ============================================================ 
#        STEP 2 — Exchange Authorization Code for Tokens 
# ============================================================ 
st.markdown("### Authorization code received!") 
st.code(auth_code) 
 
data = { 
    "client_id": CLIENT_ID, 
    "grant_type": "authorization_code", 
    "code": auth_code, 
    "code_verifier": st.session_state["code_verifier"], 
    "redirect_uri": REDIRECT_URI, 
} 
 
response = requests.post( 
    "https://api.fitbit.com/oauth2/token", 
    headers={"Content-Type": "application/x-www-form-urlencoded"}, 
    data=data 
) 
 
if response.status_code != 200: 
    st.error("Token exchange failed:") 
    st.write(response.text) 
    st.stop() 
 
tokens = response.json() 
 
st.session_state["fitbit_access_token"] = tokens["access_token"] 
st.session_state["fitbit_refresh_token"] = tokens["refresh_token"] 
st.session_state["fitbit_user_id"] = tokens["user_id"] 
 
st.success("Successfully authenticated with Fitbit!") 
st.json(tokens) 
 
 
# ============================================================ 
#                  STEP 3 — Example API Call 
# ============================================================ 
st.markdown("---") 
st.markdown("## Example API Call: User Profile") 
 
headers = {"Authorization": f"Bearer {st.session_state['fitbit_access_token']}"} 
 
profile_res = requests.get( 
    f"https://api.fitbit.com/1/user/{st.session_state['fitbit_user_id']}/profile.json", 
    headers=headers 
) 
 
if profile_res.status_code == 200: 
    st.json(profile_res.json()) 
else: 
    st.error("Failed to fetch profile:") 
    st.write(profile_res.text)

