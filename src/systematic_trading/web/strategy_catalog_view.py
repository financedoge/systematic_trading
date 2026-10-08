"""One request's role/membership reads; mutation paths always use the real store."""


class CatalogControlView:
    def __init__(self, store):
        self.store=store
        self.cache={}

    def __getattr__(self, name):
        method=getattr(self.store,name)
        if name not in {'latest_pnl_baseline','strategy_control_state'}:
            return method
        def read(*args):
            key=(name,args)
            if key not in self.cache:
                self.cache[key]=method(*args)
            return self.cache[key]
        return read
