import streamlit as st
import requests
import os
import hashlib
import base64
import urllib.parse
import boto3
import json

DEBUG_MODE = False  # Set to True when YOU want debugging

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
st.markdown(
    "<h1 style='text-align: center; color: #E8D7B9; font-size: 64px; margin-bottom: 10px;'>"
    "Welcome to the Heat Stress Research Study!"
    "</h1>",
    unsafe_allow_html=True
)

st.markdown('<div class="subheader">Fitbit Authorization Page</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="normal-text">
        You’ll use this page to securely connect your Fitbit account.
        After you log in and approve the connection, the app will automatically access the Fitbit data needed for the study. 
        Your information is handled safely and used only for research purposes.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subheader" style="margin-top: 40px;">'
    'To get started, connect your Fitbit account below.'
    '</div>',
    unsafe_allow_html=True
)


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

# --- AWS config from secrets (with sane defaults) ---
AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = st.secrets["AWS_REGION"]

# default to your bucket + a 'tokens/' prefix if not set in secrets.toml
S3_BUCKET_NAME = st.secrets.get("S3_BUCKET_NAME", "fitbit-study-tokens-stored")
S3_TOKEN_PREFIX = st.secrets.get("S3_TOKEN_PREFIX", "tokens/")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

# ============================================================
#        OPTIONAL: S3 CONNECTIVITY TEST (DEV ONLY)
# ============================================================
if DEBUG_MODE:
    with st.expander("Developer check: S3 connectivity test", expanded=False):
        try:
            resp = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=S3_TOKEN_PREFIX)
            st.success("S3 connection successful ✅")
            st.write("Objects under that prefix (may be empty):")
            st.write(resp.get("Contents", []))
        except Exception as e:
            st.error("S3 connection FAILED ❌")
            st.write(str(e))


# ============================================================
#                PKCE GENERATION HELPERS
# ============================================================
def generate_code_verifier() -> str:
    """Generate a 43–128 character URL-safe string."""
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8")
    return verifier.rstrip("=")


def generate_code_challenge(verifier: str) -> str:
    """SHA256 + Base64URL → code challenge"""
    sha256 = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(sha256).decode("utf-8")
    return challenge.rstrip("=")


# ============================================================
#                   STREAMLIT APP UI
# ============================================================
params = st.query_params


def _first_or_none(value):
    if value is None:
        return None
    if isinstance(value, list):
        return value[0]
    return value


auth_code = _first_or_none(params.get("code"))
returned_state = _first_or_none(params.get("state"))

# ============================================================
#                STEP 1 — Show Fitbit Login Link
# ============================================================
if not auth_code:
    # Create a fresh verifier + challenge
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # We send the verifier itself in the `state` parameter so we can
    # recover it reliably on the callback, even if session_state is lost.
    state_value = code_verifier

    auth_url = (
        "https://www.fitbit.com/oauth2/authorize?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope={urllib.parse.quote(SCOPES)}&"
        f"code_challenge={code_challenge}&"
        "code_challenge_method=S256&"
        f"state={urllib.parse.quote(state_value)}"
    )

    # Centered, styled button
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 25px;">
            <a href="{auth_url}"
               style="
                    background-color: #4CAF50;
                    color: white;
                    padding: 15px 30px;
                    border-radius: 10px;
                    font-size: 24px;
                    font-weight: bold;
                    text-decoration: none;
                    display: inline-block;
               ">
               Connect with Fitbit
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# ============================================================
#        STEP 2 — Exchange Authorization Code for Tokens
# ============================================================
code_verifier = returned_state or st.session_state.get("code_verifier")

if not code_verifier:
    st.error(
        "Something went wrong while verifying your connection. "
        "Please go back to the start page and try connecting again."
    )
    st.stop()

data = {
    "client_id": CLIENT_ID,
    "grant_type": "authorization_code",
    "code": auth_code,
    "code_verifier": code_verifier,
    "redirect_uri": REDIRECT_URI,
}

response = requests.post(
    "https://api.fitbit.com/oauth2/token",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data=data,
)

if response.status_code != 200:
    st.error("We couldn't finish connecting to Fitbit.")
    st.write("Please try again. If this keeps happening, contact the study team.")
    if DEBUG_MODE:
        st.write("DEBUG: Fitbit token endpoint response text:")
        st.write(response.text)
    st.stop()

tokens = response.json()

# Debug only: show raw token response
if DEBUG_MODE:
    st.write(
        "DEBUG: raw token response from Fitbit "
        "(do NOT screenshot this with real data in production):"
    )
    st.write(tokens)

# Store tokens in session_state (not shown to user)
st.session_state["fitbit_access_token"] = tokens.get("access_token")
st.session_state["fitbit_refresh_token"] = tokens.get("refresh_token")
st.session_state["fitbit_user_id"] = tokens.get("user_id")

# ==========================
# SAVE TOKENS TO S3
# ==========================
user_id = tokens.get("user_id")

if not user_id:
    # User-friendly message
    st.error(
        "We were not able to complete the connection to your Fitbit account. "
        "Please try again, and if the issue continues, contact the study team."
    )
    if DEBUG_MODE:
        st.write("DEBUG: No user_id found in token response; cannot save to S3.")
else:
    s3_key = f"{S3_TOKEN_PREFIX}{user_id}.json"

    if DEBUG_MODE:
        st.write("DEBUG: Preparing to upload token file to S3...")
        st.write("DEBUG: S3 bucket:", S3_BUCKET_NAME)
        st.write("DEBUG: S3 key:", s3_key)

    token_payload = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "user_id": user_id,
    }

    try:
        response_s3 = s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(token_payload),
            ContentType="application/json",
        )
        if DEBUG_MODE:
            st.success("Tokens saved securely for the study team. ✔️")
            st.write("DEBUG: S3 put_object response:")
            st.write(response_s3)
    except Exception as e:
        st.error(
            "We couldn't save your Fitbit connection to our secure storage. "
            "Please try again later or contact the study team."
        )
        if DEBUG_MODE:
            st.write("DEBUG: S3 upload error:")
            st.write(str(e))

# ============================================================
#        CLEAN SUCCESS MESSAGE FOR PARTICIPANTS
# ============================================================
st.markdown(
    """
    <div style="text-align: center;">
        <div style="
            background-color: #e8f8ee;
            padding: 20px;
            border-radius: 12px;
            display: inline-block;
            font-size: 22px;
            color: #1b7a4e;
            font-weight: 500;
            margin-top: 20px;
        ">
            You're all set! Your Fitbit account is now connected.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div style="text-align: center; margin-top: 40px;">
        <h2 style="font-weight: 700; font-size: 42px; margin-bottom: 10px;">
            You can close this page now.
        </h2>
        <p style="font-size: 22px; color: #444;">
            Thank you for completing the Fitbit connection step.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
