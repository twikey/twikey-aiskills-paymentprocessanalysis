# Payment X-ray, by Twikey

A free plugin for Claude Code, for companies that already collect by direct debit.

It shows where your payment process leaks, counted from your own exports: failed collections and why, expired
mandates, payments that match no invoice, invoices paid twice, customers who pay later than agreed, and the manual
steps each finding asks for. Then it prepares this month's work for you: new attempts with a suggested collection
day, one mail draft per customer, mandates to renew and match suggestions. It reads the exports on your own
computer and never sends anything. Claude Code on macOS or Linux.

Full details: [plugins/twikey-payment-xray/README.md](plugins/twikey-payment-xray/README.md).

## Install in Claude Code

The plugin is in Twikey's public repository on GitHub:
https://github.com/twikey/twikey-aiskills-paymentprocessanalysis. Its marketplace is called `twikey-xray`. In a
terminal, add it as a marketplace, then install the plugin:

```
claude plugin marketplace add twikey/twikey-aiskills-paymentprocessanalysis
claude plugin install twikey-payment-xray@twikey-xray
```

Or download the repository as a ZIP from that GitHub page, unzip it, open a terminal in the folder that holds the
unzipped folder, and run:

```
claude plugin marketplace add ./<unzipped folder>
claude plugin install twikey-payment-xray@twikey-xray
```

To try the plugin for one session without installing it, start Claude Code with `--plugin-dir` followed by the
path to the plugin's folder.

## License

MIT, see `LICENSE`.
