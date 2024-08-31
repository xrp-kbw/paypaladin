from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet, generate_faucet_wallet
import xrpl
from .config import JSON_RPC_URL

client = JsonRpcClient(JSON_RPC_URL)

def generate_faucet_wallet_sync(client, debug):
    return generate_faucet_wallet(client, debug=debug)

def send_xrp(seed, amount, destination):
    sending_wallet = Wallet.from_seed(seed)
    payment = xrpl.models.transactions.Payment(
        account=sending_wallet.address,
        amount=xrpl.utils.xrp_to_drops(int(amount)),
        destination=destination,
    )
    try:    
        response = xrpl.transaction.submit_and_wait(payment, client, sending_wallet)    
    except xrpl.transaction.XRPLReliableSubmissionException as e:    
        response = f"Submit failed: {e}"
    return response
