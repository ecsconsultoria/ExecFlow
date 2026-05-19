def register_blueprints(app):
    from .auth          import auth_bp
    from .dashboard     import dashboard_bp
    from .clients       import clients_bp
    from .suppliers     import suppliers_bp
    from .drivers       import drivers_bp
    from .vehicles      import vehicles_bp
    from .categories    import categories_bp
    from .services      import services_bp
    from .quotes        import quotes_bp
    from .bookings      import bookings_bp
    from .financial     import financial_bp
    from .reports       import reports_bp
    from .service_orders import service_orders_bp
    from .dispatch       import dispatch_bp

    app.register_blueprint(auth_bp,           url_prefix="/auth")
    app.register_blueprint(dashboard_bp,      url_prefix="/")
    app.register_blueprint(clients_bp,        url_prefix="/clients")
    app.register_blueprint(suppliers_bp,      url_prefix="/suppliers")
    app.register_blueprint(drivers_bp,        url_prefix="/drivers")
    app.register_blueprint(vehicles_bp,       url_prefix="/vehicles")
    app.register_blueprint(categories_bp,     url_prefix="/categories")
    app.register_blueprint(services_bp,       url_prefix="/services")
    app.register_blueprint(quotes_bp,         url_prefix="/quotes")
    app.register_blueprint(bookings_bp,       url_prefix="/bookings")
    app.register_blueprint(financial_bp,      url_prefix="/financial")
    app.register_blueprint(reports_bp,        url_prefix="/reports")
    app.register_blueprint(service_orders_bp, url_prefix="/os")
    app.register_blueprint(dispatch_bp,       url_prefix="/dispatch")
