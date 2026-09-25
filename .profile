# requirements.txt (exported from Poetry) only lists third-party deps, so the
# python_buildpack's `pip install -r requirements.txt` never installs this
# project's own `invoice_processing` package. The buildpack's own profile.d script
# unconditionally sets PYTHONPATH, so appending src/ has to happen here: CF sources
# this file *after* the buildpack's profile.d scripts, right before exec'ing the
# start command (see cloudfoundry/buildpackapplifecycle launcher_unix.go).
export PYTHONPATH="$PYTHONPATH:$PWD/src"
