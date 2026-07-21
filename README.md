### XpertIntegration

XpertIntegration is an all-in-one communication and data synchronization platform designed to bridge the gaps between your digital tools. By centralizing messaging and automating seamless data transfers across disparate platforms, XpertIntegration eliminates silos, boosts productivity, and ensures your information is always exactly where you need it—whenever you need it.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app xpertintegration
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/xpertintegration
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
