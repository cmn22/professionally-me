from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from typing import Any, Callable

# Use LiteLLM's bundled model metadata instead of fetching it during startup.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from litellm.integrations.custom_logger import CustomLogger


class LLMConfigurationError(ValueError):
    """Raised when the LiteLLM Router configuration is invalid."""


class LLMServiceError(RuntimeError):
    """A safe, user-facing description of an LLM provider failure."""


class DeploymentLogger(CustomLogger):
    """Log routing attempts without recording prompts, responses, or API keys."""

    @staticmethod
    def _model(model: str | None, kwargs: dict[str, Any]) -> str:
        return model or str(kwargs.get("model") or "unknown")

    @staticmethod
    def _status(response_obj: Any) -> str:
        status_code = getattr(response_obj, "status_code", None)
        if status_code is None:
            response = getattr(response_obj, "response", None)
            status_code = getattr(response, "status_code", None)
        return str(status_code) if status_code is not None else "unknown"

    def log_pre_api_call(self, model, messages, kwargs):
        print(f"LLM deployment attempt: model={self._model(model, kwargs)}", flush=True)

    async def async_log_pre_api_call(self, model, messages, kwargs):
        self.log_pre_api_call(model, messages, kwargs)

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        print(
            f"LLM deployment succeeded: model={self._model(None, kwargs)}",
            flush=True,
        )

    async def async_log_success_event(
        self, kwargs, response_obj, start_time, end_time
    ):
        self.log_success_event(kwargs, response_obj, start_time, end_time)

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        exception = response_obj or kwargs.get("exception")
        print(
            "LLM deployment failed: "
            f"model={self._model(None, kwargs)} "
            f"error={type(exception).__name__} "
            f"status={self._status(exception)}",
            flush=True,
        )

    async def async_log_failure_event(
        self, kwargs, response_obj, start_time, end_time
    ):
        self.log_failure_event(kwargs, response_obj, start_time, end_time)


deployment_logger = DeploymentLogger(turn_off_message_logging=True)
if not any(isinstance(callback, DeploymentLogger) for callback in litellm.callbacks):
    litellm.callbacks.append(deployment_logger)


@dataclass(frozen=True)
class LLMConfig:
    model_group: str
    model_list: list[dict[str, Any]]
    router_settings: dict[str, Any]

    @classmethod
    def from_app_config(cls, config: dict[str, Any]) -> "LLMConfig":
        llm_config = config.get("llm")
        if not isinstance(llm_config, dict):
            raise LLMConfigurationError(
                "config.json must contain an 'llm' Router configuration."
            )

        model_group = str(llm_config.get("model_group", "")).strip()
        model_list = llm_config.get("model_list")
        router_settings = llm_config.get("router_settings", {})

        if not model_group:
            raise LLMConfigurationError("The LiteLLM model_group cannot be empty.")
        if not isinstance(model_list, list) or not model_list:
            raise LLMConfigurationError(
                "The LiteLLM model_list must contain at least one deployment."
            )
        if not isinstance(router_settings, dict):
            raise LLMConfigurationError("LiteLLM router_settings must be an object.")

        for index, deployment in enumerate(model_list, start=1):
            if not isinstance(deployment, dict):
                raise LLMConfigurationError(
                    f"LiteLLM deployment {index} must be an object."
                )
            if deployment.get("model_name") != model_group:
                raise LLMConfigurationError(
                    f"LiteLLM deployment {index} must use model_name "
                    f"'{model_group}'."
                )

            params = deployment.get("litellm_params")
            if not isinstance(params, dict) or not params.get("model"):
                raise LLMConfigurationError(
                    f"LiteLLM deployment {index} must define litellm_params.model."
                )

            order = params.get("order")
            if not isinstance(order, int) or order < 1:
                raise LLMConfigurationError(
                    f"LiteLLM deployment {index} must have a positive integer order."
                )

        return cls(
            model_group=model_group,
            model_list=deepcopy(model_list),
            router_settings=deepcopy(router_settings),
        )


class LiteLLMClient:
    def __init__(
        self,
        config: LLMConfig,
        router_factory: Callable[..., Any] = litellm.Router,
    ):
        self.config = config
        self.router = router_factory(
            model_list=config.model_list,
            **config.router_settings,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            response = self.router.completion(
                model=self.config.model_group,
                messages=messages,
                tools=tools,
            )
        except litellm.AuthenticationError as exc:
            raise LLMServiceError(
                "LLM authentication failed. Check the API keys required by the "
                "configured deployments."
            ) from exc
        except litellm.RateLimitError as exc:
            raise LLMServiceError(
                "All configured LLM deployments are temporarily rate-limited. "
                "Please retry shortly."
            ) from exc
        except (
            litellm.ServiceUnavailableError,
            litellm.InternalServerError,
            litellm.BadGatewayError,
        ) as exc:
            raise LLMServiceError(
                "All configured LLM deployments are temporarily unavailable. "
                "Please retry shortly."
            ) from exc
        except litellm.APIConnectionError as exc:
            raise LLMServiceError(
                "Could not connect to any configured LLM deployment. Please retry "
                "shortly."
            ) from exc
        except litellm.APIError as exc:
            raise LLMServiceError(
                "No configured LLM deployment could complete the request."
            ) from exc
        except Exception as exc:
            print(
                f"LLM routing failed: error={type(exc).__name__}",
                flush=True,
            )
            raise LLMServiceError(
                "No configured LLM deployment could complete the request."
            ) from exc

        message = response.choices[0].message
        if hasattr(message, "model_dump"):
            return message.model_dump(exclude_none=True)
        return dict(message)
