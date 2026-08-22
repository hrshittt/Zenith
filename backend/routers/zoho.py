import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from backend.models.domain import User
from backend.core.auth import get_current_user
from urllib.parse import urlencode

router = APIRouter(prefix="/api/zoho", tags=["Zoho"])

ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")

# The base URL could be different based on the DC (e.g., accounts.zoho.com, accounts.zoho.eu, accounts.zoho.in)
# Using accounts.zoho.in for India region, which is common for Indian users, but it can be parameterized later.
ZOHO_AUTH_URL = "https://accounts.zoho.in/oauth/v2/auth"
ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
ZOHO_SCOPE = "ZohoBooks.fullaccess.all"

@router.get("/auth")
def zoho_auth():
    if not ZOHO_CLIENT_ID or not ZOHO_CLIENT_SECRET or not ZOHO_REDIRECT_URI:
        raise HTTPException(
            status_code=500, 
            detail="Zoho OAuth credentials are not configured on the backend."
        )

    params = {
        "scope": ZOHO_SCOPE,
        "client_id": ZOHO_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": ZOHO_REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent"
    }
    
    url = f"{ZOHO_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url)

@router.get("/callback")
def zoho_callback(code: str = None, error: str = None):
    if error:
        # Redirect back to frontend with error
        return RedirectResponse("http://localhost:5503/register.html?zoho=error")

    if not code:
        return RedirectResponse("http://localhost:5503/register.html?zoho=error")

    # Exchange code for token
    data = {
        "code": code,
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "redirect_uri": ZOHO_REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    try:
        res = requests.post(ZOHO_TOKEN_URL, data=data)
        res_data = res.json()

        if "access_token" in res_data:
            access_token = res_data["access_token"]
            
            try:
                # 1. Fetch Organization ID
                org_res = requests.get(
                    "https://www.zohoapis.in/books/v3/organizations",
                    headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                )
                org_data = org_res.json()
                if org_data.get("code") != 0 or not org_data.get("organizations"):
                    return RedirectResponse("http://localhost:5503/register.html?zoho=error&msg=no_org")
                
                org_id = org_data["organizations"][0]["organization_id"]

                # 2. Fetch Bank Accounts (Current Cash)
                bank_res = requests.get(
                    f"https://www.zohoapis.in/books/v3/bankaccounts?organization_id={org_id}",
                    headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                )
                bank_data = bank_res.json()
                
                total_cash = 0.0
                if bank_data.get("code") == 0:
                    for acc in bank_data.get("bankaccounts", []):
                        # Sum up base currency balance
                        total_cash += float(acc.get("bcy_balance", 0) or 0)

                # 3. Fetch Profit & Loss (Revenue and Burn)
                # We request this month's P&L
                pnl_res = requests.get(
                    f"https://www.zohoapis.in/books/v3/reports/profitandloss?organization_id={org_id}&filter_by=ThisMonth",
                    headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
                )
                pnl_data = pnl_res.json()
                
                total_income = 0.0
                total_expense = 0.0
                
                if pnl_data.get("code") == 0:
                    profit_loss = pnl_data.get("profitandloss", {})
                    # Usually "Total Income" and "Total Expense" are in the summary
                    # Fallback to 0 if not easily parseable
                    total_income = float(profit_loss.get("total_income", 0) or 0)
                    total_expense = float(profit_loss.get("total_expense", 0) or 0)

                # Redirect back with the real data!
                # If they just created a blank Zoho account, numbers will be 0.
                # In that case, we can let the frontend handle it (maybe prompt them to manually enter).
                return RedirectResponse(f"http://localhost:5503/register.html?zoho=success&cash={total_cash}&rev={total_income}&burn={total_expense}")

            except Exception as e:
                print("Zoho API Fetch Error:", e)
                return RedirectResponse("http://localhost:5503/register.html?zoho=error&msg=api_fail")
        else:
            return RedirectResponse("http://localhost:5503/register.html?zoho=error")
    except Exception as e:
        print("Zoho Token Error:", e)
        return RedirectResponse("http://localhost:5503/register.html?zoho=error")
