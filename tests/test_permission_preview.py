from types import SimpleNamespace

import pytest
from ibapi.client import EClient

from systematic_trading.execution import permission_preview as module


@pytest.mark.parametrize('reported_account', ['DU123', 'U123', 'DU456'])
def test_preview_is_hardcoded_whatif_and_requires_exact_paper_account(monkeypatch, reported_account):
    sent=[]
    monkeypatch.setattr(module,'InteractiveBrokersAdapter',lambda _:SimpleNamespace(
        profile_for=lambda _:SimpleNamespace(host='localhost',port=4002)))
    monkeypatch.setattr(EClient,'connect',lambda self,*args:self.nextValidId(1))
    monkeypatch.setattr(EClient,'run',lambda self:None)
    monkeypatch.setattr(EClient,'disconnect',lambda self:None)
    monkeypatch.setattr(EClient,'reqManagedAccts',lambda self:self.managedAccounts(reported_account))
    def place(self,request,contract,order):
        sent.append(order)
        assert order.whatIf is True and order.transmit is True
        assert order.account=='DU123' and order.totalQuantity==1
        assert contract.conId==42 and contract.exchange=='SMART'
        self.openOrder(request,contract,order,SimpleNamespace(status='PreSubmitted',
            initMarginAfter='100',maintMarginAfter='100',warningText=''))
    monkeypatch.setattr(EClient,'placeOrder',place)
    identities={'NEW':dict(status='identity_verified',details=dict(contract=dict(
        conId=42,symbol='NEW',secType='STK',currency='USD',primaryExchange='ARCA')))}
    if reported_account=='DU123':
        result=module.preview_permissions(None,identities,account='DU123')
        assert result['NEW']['what_if'] is True and not result['NEW']['errors']
        assert len(sent)==1
    else:
        with pytest.raises(ValueError,match='account mismatch'):
            module.preview_permissions(None,identities,account='DU123')
        assert not sent
    with pytest.raises(ValueError,match='Paper account required'):
        module.preview_permissions(None,identities,account='U123')
