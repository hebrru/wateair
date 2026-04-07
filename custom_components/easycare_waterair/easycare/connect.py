"""Class used to manage all calls to Easy-Care API."""

import json
import logging
from pathlib import Path
import hashlib
import re
import time
from urllib.parse import parse_qs, urlparse

import requests

from homeassistant.core import HomeAssistant

from .config import EasyCareConfig

_LOGGER = logging.getLogger("custom_components.ha-easycare-waterair")

bearerstore = ".easycarebearer"

SSO_AUTHORIZE_URL = (
    "https://sso.waterair.com/waterairexternb2c.onmicrosoft.com/"
    "b2c_1a_signup_signin_inter/oauth2/v2.0/authorize"
)
SSO_TOKEN_URL = (
    "https://sso.waterair.com/waterairexternb2c.onmicrosoft.com/"
    "b2c_1a_signup_signin_inter/oauth2/v2.0/token"
)
SSO_POLICY = "B2C_1A_signup_signin_inter"
SSO_CLIENT_ID = "6c015150-c33f-463e-89bc-6ad5614bdc15"
SSO_REDIRECT_URI = "msauth.com.waterair.easycare://auth"
SSO_SCOPE = (
    "https://sso.waterair.com/api/openid "
    "https://sso.waterair.com/api/offline_access openid profile offline_access"
)
SSO_CODE_CHALLENGE = "nKnk64mx1G_lEG5cshhNggBm-PAf9UZnZayLNtux2Bc"
SSO_CODE_VERIFIER = "w-j6efyTpo1umXD0hFZPRM8l7kD9yScwZ3E5rAHJuE4"
EASYCARE_BASIC_AUTH = (
    "Basic NWQwMjFkYzI0NzhjMjE3MDc3MzI0NDEwOkNtVmZxNDNiZE5hUUZjWA=="
)


class Connect:
    """Class is used to manage all calls to Easy-Care API."""

    def __init__(self, config: EasyCareConfig, hass: HomeAssistant) -> None:
        """Create the class.

        Args:
            config (EasyCareConfig): Configuration variables.
            hass (HomeAssistant): The hass object

        """
        self._hass = hass
        self._config = config
        self._bearer_timeout = -1
        self._bearer = None
        self._is_connected = False
        self._user_json = None
        self._modules = None
        self._bpc_modules = None
        self._call_light_change = False

    def _get_bearer_file_path(self) -> Path:
        """Return the bearer cache file path."""
        if self._config.username == self._config.unset:
            return Path(self._hass.config.config_dir) / bearerstore

        username_hash = hashlib.sha256(
            self._config.username.lower().encode("utf-8")
        ).hexdigest()[:12]
        return Path(self._hass.config.config_dir) / f"{bearerstore}_{username_hash}"

    def login(self) -> bool:
        """Login to Easy-Care and store the bearer."""

        if self._check_bearer() is True:
            _LOGGER.debug("Bearer is defined, no need to login !")
            self._is_connected = True
            return True

        bearer_path = self._get_bearer_file_path()
        if bearer_path.is_file() is True:
            _LOGGER.debug("Bearer is stored in file, try to read it")
            with bearer_path.open("r", encoding="utf-8") as f:
                self._bearer = f.readline().strip() or None
                bearer_timeout = f.readline().strip()
            if bearer_timeout != "":
                self._bearer_timeout = float(bearer_timeout)
            else:
                self._bearer_timeout = -1
            if self._check_bearer() is True:
                _LOGGER.debug("Bearer is defined in file, no need to login !")
                self._is_connected = True
                return True
        else:
            bearer_path.touch(exist_ok=True)

        _LOGGER.debug("Bearer is expired or not set, calling login api")
        user = self._easycare_login()
        if user is False:
            self._is_connected = False
            return False

        self._bearer = user["access_token"]
        self._bearer_timeout = time.time() + user.get("expires_in", 3600)
        self._is_connected = True
        with bearer_path.open("w", encoding="utf-8") as f:
            f.write(self._bearer + "\n")
            f.write(str(self._bearer_timeout))

        return True

    def reset_bearer(self) -> None:
        """Remove the bearer file."""
        self._bearer = None
        self._bearer_timeout = None
        bearer_path = self._get_bearer_file_path()
        if bearer_path.is_file() is True:
            bearer_path.unlink()

    def _check_bearer(self) -> bool:
        """Check if bearer is still valid."""
        if self._bearer is None:
            return False
        if self._bearer_timeout != 0 and time.time() > self._bearer_timeout:
            self._bearer = None
            self._is_connected = False
            return False
        return True

    def _easycare_login(self) -> json:
        """Login to Easy-Care platform."""
        if self._config.token != self._config.unset:
            return self._easycare_login_via_code(self._config.token)

        if (
            self._config.username != self._config.unset
            and self._config.password != self._config.unset
        ):
            return self._easycare_login_via_credentials()

        _LOGGER.error("No EasyCare token or username/password configured.")
        return False

    def _easycare_login_via_code(self, code: str) -> json:
        """Login by exchanging the authorization code."""
        params = {
            "code": code,
            "grant_type": "authorization_code",
            "code_verifier": SSO_CODE_VERIFIER,
            "client_id": SSO_CLIENT_ID,
            "redirect_uri": SSO_REDIRECT_URI,
        }

        attempt = 0
        login = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("Get acces_token attempt #%s", attempt)
            login = requests.post(
                SSO_TOKEN_URL,
                data=params,
                timeout=3,
            )
            if login is not None and login.status_code == 200:
                break
            time.sleep(1)
        if login is None:
            _LOGGER.error("Authentication failed !")
            return False
        if login.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                login.status_code,
                login.content,
            )
            return False

        _LOGGER.debug("Get the access token done !")
        access_token = json.loads(login.content).get("id_token")
        if access_token is None:
            _LOGGER.error("Authentication response did not contain id_token")
            return False

        return self._easycare_login_via_id_token(access_token)

    def _easycare_login_via_credentials(self) -> json:
        """Login with the Waterair username and password."""
        session = requests.Session()
        auth_response = session.get(
            SSO_AUTHORIZE_URL,
            params={
                "response_type": "code",
                "code_challenge_method": "S256",
                "scope": SSO_SCOPE,
                "code_challenge": SSO_CODE_CHALLENGE,
                "redirect_uri": SSO_REDIRECT_URI,
                "client-request-id": "BDE2D6D1-8BE6-4D05-9E9B-AEADC1280CD7",
                "client_id": SSO_CLIENT_ID,
                "return-client-request-id": "true",
            },
            timeout=10,
        )
        if auth_response.status_code != 200:
            _LOGGER.error(
                "SSO authorization page failed, status_code is %s and message %s",
                auth_response.status_code,
                auth_response.content,
            )
            return False

        settings = self._extract_b2c_settings(auth_response.text)
        if settings is None:
            return False

        hosts = settings.get("hosts", {})
        tenant = hosts.get("tenant")
        policy = hosts.get("policy", SSO_POLICY)
        api = settings.get("api", "CombinedSigninAndSignup")
        csrf = settings.get("csrf")
        trans_id = settings.get("transId")
        if not tenant or not csrf or not trans_id:
            _LOGGER.error("SSO authorization page did not contain login settings")
            return False

        if not tenant.startswith("http"):
            tenant = "https://sso.waterair.com" + tenant

        headers = {
            "X-CSRF-TOKEN": csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": auth_response.url,
        }
        login = session.post(
            tenant + "/SelfAsserted",
            params={"tx": trans_id, "p": policy},
            data={
                "request_type": "RESPONSE",
                "signInName": self._config.username,
                "password": self._config.password,
            },
            headers=headers,
            timeout=10,
        )
        if login.status_code != 200:
            _LOGGER.error(
                "SSO credentials login failed, status_code is %s and message %s",
                login.status_code,
                login.content,
            )
            return False

        try:
            login_result = login.json()
        except ValueError:
            _LOGGER.error(
                "SSO credentials login returned invalid JSON: %s", login.content
            )
            return False

        if str(login_result.get("status")) != "200":
            _LOGGER.error(
                "SSO credentials login failed: %s",
                login_result.get("message", login.content),
            )
            return False

        confirmed = session.get(
            tenant + "/api/" + api + "/confirmed",
            params={
                "rememberMe": "false",
                "csrf_token": csrf,
                "tx": trans_id,
                "p": policy,
            },
            headers={"Referer": auth_response.url},
            allow_redirects=False,
            timeout=10,
        )

        redirect_url = confirmed.headers.get("Location")
        if not redirect_url:
            _LOGGER.error(
                "SSO confirmation did not redirect, status_code is %s and message %s",
                confirmed.status_code,
                confirmed.content,
            )
            return False

        code = parse_qs(urlparse(redirect_url).query).get("code", [None])[0]
        if code is None:
            _LOGGER.error("SSO redirect did not contain an authorization code")
            return False

        return self._easycare_login_via_code(code)

    @staticmethod
    def _extract_b2c_settings(page_content):
        """Extract the Azure B2C settings embedded in the login page."""
        match = re.search(r"var\s+SETTINGS\s*=\s*({.*?});", page_content, re.DOTALL)
        if match is None:
            _LOGGER.error("Unable to find SSO settings in authorization page")
            return None

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            _LOGGER.exception("Unable to parse SSO settings from authorization page")
            return None

    def _easycare_login_via_id_token(self, access_token: str) -> json:
        """Exchange the Azure B2C id token for an EasyCare bearer."""

        headers = {
            "authorization": EASYCARE_BASIC_AUTH,
        }
        attempt = 0
        login = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("Get bearer attempt #%s", attempt)
            login = requests.post(
                self._config.host + "/oauth2/tokenFromAzureADB2CIdToken",
                json={
                    "idToken": access_token,
                },
                headers=headers,
                timeout=3,
            )
            if login is not None:
                break
            time.sleep(1)
        if login is None:
            _LOGGER.error("Authentication failed !")
            return False
        if login.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                login.status_code,
                login.content,
            )
            return False

        _LOGGER.debug("Get the bearer done !")

        return json.loads(login.content)

    def get_connection_status(self) -> bool:
        """Return the connextion status for Easy-Care."""
        return self._is_connected

    def get_bearer(self) -> bool:
        """Return the bearer for Easy-Care."""
        return self._bearer

    def get_user_json(self) -> json:
        """Return the user json for Easy-Care."""
        return self._user_json

    def get_modules(self) -> json:
        """Return the modules for Easy-Care."""
        if self._modules is not None:
            return self._modules

        self.easycare_update_modules()
        return self._modules

    def get_bpc_modules(self) -> json:
        """Return the modules for Easy-Care."""
        if self._bpc_modules is not None:
            return self._bpc_modules

        self.easycare_update_bpc_modules()
        return self._bpc_modules

    def easycare_update_modules(self) -> None:
        """Get modules detail by calling getUserWithHisModules."""
        if self._check_bearer() is False:
            self.login()

        if self._is_connected is False:
            return

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "connected-pool-waterair/2.4.6 (iPad; iOS 16.3; Scale/2.00)",
            "authorization": "Bearer " + self._bearer,
            "accept": "version=2.5",
        }

        attempt = 0
        modules = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("getUserWithHisModules attempt #%s", attempt)
            modules = requests.get(
                self._config.host + "/api/getUserWithHisModules",
                headers=headers,
                timeout=3,
            )
            if modules is not None:
                break
            time.sleep(1)
        if modules is None:
            _LOGGER.error("Error calling getUserWithHisModules")
            return
        if modules.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                modules.status_code,
                modules.content,
            )
            return
        json_modules = json.loads(modules.content)
        self._modules = json_modules["modules"]
        _LOGGER.debug("getUserWithHisModules done !")

    def easycare_update_user(self) -> None:
        """Get User detail by calling getUser."""
        if self._check_bearer() is False:
            self.login()

        if self._is_connected is False:
            _LOGGER.debug("EasyCare server unavailable !")
            return

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "connected-pool-waterair/2.4.6 (iPad; iOS 16.3; Scale/2.00)",
            "authorization": "Bearer " + self._bearer,
            "accept": "version=2.5",
        }

        attempt = 0
        user = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("GetUser attempt #%s", attempt)
            user = requests.get(
                self._config.host + "/api/getUser?attributesToPopulate%5B%5D=pools",
                headers=headers,
                timeout=5,
            )
            if user is not None:
                break
            time.sleep(1)
        if user is None:
            _LOGGER.error("Error calling getUser")
            self._is_connected = False
            return
        if user.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                user.status_code,
                user.content,
            )
            self._is_connected = False
            return

        self._user_json = json.loads(user.content)
        _LOGGER.debug("GetUser done !")

    def easycare_update_bpc_modules(self) -> None:
        """Return the modules for Easy-Care."""
        if self._call_light_change is True:
            return

        if self._check_bearer() is False:
            self.login()

        if self._is_connected is False:
            return

        watbox_serial_number = None
        bpc_name = None

        if self._modules is None:
            return

        for module in self._modules:
            if module["type"] == "lr-bst-compact":
                watbox_serial_number = module["serialNumber"]
            if module["type"] == "lr-pc":
                bpc_name = module["name"][4::]

        if bpc_name is None:
            return

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "connected-pool-waterair/2.4.6 (iPad; iOS 16.3; Scale/2.00)",
            "authorization": "Bearer " + self._bearer,
            "accept": "version=2.5",
        }

        attempt = 0
        bpc_modules = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("getBPCModules attempt #%s", attempt)
            bpc_modules = requests.get(
                self._config.host
                + "/api/module/"
                + watbox_serial_number
                + "/status/"
                + bpc_name,
                headers=headers,
                timeout=3,
            )
            if bpc_modules is not None:
                break
            time.sleep(1)
        if bpc_modules is None:
            _LOGGER.error("Error calling getBPCModules")
            return
        if bpc_modules.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                bpc_modules.status_code,
                bpc_modules.content,
            )
            return
        json_modules = json.loads(bpc_modules.content)
        self._bpc_modules = json_modules["pool"]
        _LOGGER.debug("getBPCModules done !")

    def turn_on_light(self, modules, light_id) -> bool:
        """Turn on the light."""
        duration = 3600
        if light_id == 1:
            # Spot duration
            number = self._hass.states.get(
                "number.easy_care_pool_spot_light_duration_in_hours"
            )
            if number is not None:
                duration = int(float(number.state)) * 3600
        if light_id == 2:
            # Spot duration
            number = self._hass.states.get(
                "number.easy_care_pool_escalight_light_duration_in_hours"
            )
            if number is not None:
                duration = int(float(number.state)) * 3600

        if modules is None:
            return False

        if self._check_bearer() is False:
            self.login()

        if self._is_connected is False:
            return False

        watbox_serial_number = None
        bpc_name = None
        bpc_id = None
        self._call_light_change = True
        for module in modules:
            if module.type == "lr-bst-compact":
                watbox_serial_number = module.serial_number
            if module.type == "lr-pc":
                bpc_name = module.name[4::]
                bpc_id = module.id

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "connected-pool-waterair/2.4.6 (iPad; iOS 16.3; Scale/2.00)",
            "authorization": "Bearer " + self._bearer,
            "accept": "version=2.5",
        }

        body = {"pool": {"index": light_id, "manualDuration": duration, "action": 2}}

        confirm_body = {
            "command": {
                "pool": {"manualDuration": duration, "index": light_id, "action": 2}
            },
            "route": "http",
            "id": bpc_id,
        }

        attempt = 0
        result = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("TurnOnLight attempt #%s", attempt)
            result = requests.post(
                self._config.host
                + "/api/module/"
                + watbox_serial_number
                + "/manual/"
                + bpc_name,
                headers=headers,
                json=body,
                timeout=3,
            )
            if result is not None:
                break
            time.sleep(1)
        if result is None:
            _LOGGER.error("Error calling TurnOnLight")
            self._call_light_change = False
            return False
        if result.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                result.status_code,
                result.content,
            )
            self._call_light_change = False
            return False

        # Now call confirmation
        attempt = 0
        result = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("ConfirmationCall attempt #%s", attempt)
            result = requests.post(
                self._config.host + "/api/reportManualCommandSent",
                headers=headers,
                json=confirm_body,
                timeout=3,
            )
            if result is not None:
                break
            time.sleep(1)
        if result is None:
            _LOGGER.error("Error calling ConfirmationCall")
            self._call_light_change = False
            return False
        if result.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                result.status_code,
                result.content,
            )
            self._call_light_change = False
            return False

        self.easycare_update_bpc_modules()
        _LOGGER.debug("turnOnLight done !")
        self._bpc_modules = None
        self._call_light_change = False
        return True

    def turn_off_light(self, modules, light_id) -> bool:
        """Turn on the light."""
        if modules is None:
            return False

        if self._check_bearer() is False:
            self.login()

        if self._is_connected is False:
            return False

        watbox_serial_number = None
        bpc_name = None
        bpc_id = None
        self._call_light_change = True

        for module in modules:
            if module.type == "lr-bst-compact":
                watbox_serial_number = module.serial_number
            if module.type == "lr-pc":
                bpc_name = module.name[4::]
                bpc_id = module.id

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "connected-pool-waterair/2.4.6 (iPad; iOS 16.3; Scale/2.00)",
            "authorization": "Bearer " + self._bearer,
            "accept": "version=2.5",
        }

        body = {"pool": {"index": light_id, "action": 1}}

        confirm_body = {
            "command": {"pool": {"index": light_id, "action": 1}},
            "route": "http",
            "id": bpc_id,
        }

        attempt = 0
        result = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("TurnOffLight attempt #%s", attempt)
            result = requests.post(
                self._config.host
                + "/api/module/"
                + watbox_serial_number
                + "/manual/"
                + bpc_name,
                headers=headers,
                json=body,
                timeout=3,
            )
            if result is not None:
                break
            time.sleep(1)
        if result is None:
            _LOGGER.error("Error calling TurnOffLight")
            self._call_light_change = False
            return False
        if result.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                result.status_code,
                result.content,
            )
            self._call_light_change = False
            return False

        # Now call confirmation
        attempt = 0
        result = None
        while attempt < 3:
            attempt += 1
            _LOGGER.debug("ConfirmationCall attempt #%s", attempt)
            result = requests.post(
                self._config.host + "/api/reportManualCommandSent",
                headers=headers,
                json=confirm_body,
                timeout=3,
            )
            if result is not None:
                break
            time.sleep(1)
        if result is None:
            _LOGGER.error("Error calling ConfirmationCall")
            self._call_light_change = False
            return False
        if result.status_code != 200:
            _LOGGER.error(
                "Request failed, status_code is %s and message %s",
                result.status_code,
                result.content,
            )
            self._call_light_change = False
            return False

        self.easycare_update_bpc_modules()
        _LOGGER.debug("TurnOffLight done !")
        self._bpc_modules = None
        self._call_light_change = False
        return True
