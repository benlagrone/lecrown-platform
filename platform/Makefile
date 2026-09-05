CRM_ENV_FILE ?= ops/espocrm/.env
CRM_SCRIPT = ops/espocrm/crm.sh

.PHONY: crm-init-env crm-up crm-down crm-pull crm-build crm-upgrade crm-logs crm-ps gov-contracts-refresh

crm-init-env:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) init-env

crm-up:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) up

crm-down:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) down

crm-pull:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) pull

crm-build:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) build

crm-upgrade:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) upgrade

crm-logs:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) logs

crm-ps:
	@CRM_ENV_FILE=$(CRM_ENV_FILE) bash $(CRM_SCRIPT) ps

gov-contracts-refresh:
	cd backend && python3 -m app.jobs.refresh_gov_contracts --window-days 7
