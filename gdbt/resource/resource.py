import abc
import typing

import attr
import deserialize  # type: ignore
import grafana_api.grafana_api  # type: ignore

import gdbt.errors

# import gdbt.provider.provider

IGNORED_KEYS = ["id", "uid", "version"]


@deserialize.downcast_field("kind")
@attr.s
class Resource(abc.ABC):
    grafana: str = attr.ib()
    uid: str = attr.ib()
    model: typing.Dict[str, typing.Any] = attr.ib()

    @abc.abstractclassmethod
    def get(
        cls,
        grafana: str,
        uid: str,
        providers: typing.Dict[str, typing.Any],
    ) -> "Resource":
        pass

    @abc.abstractclassmethod
    def exists(
        cls,
        grafana: str,
        uid: str,
        providers: typing.Dict[str, typing.Any],
    ) -> bool:
        pass

    @abc.abstractmethod
    def id(self, providers: typing.Dict[str, typing.Any]) -> int:
        pass

    @abc.abstractmethod
    def update(
        self,
        model: typing.Dict[str, typing.Any],
        providers: typing.Dict[str, typing.Any],
    ) -> None:
        pass

    @abc.abstractmethod
    def delete(self, providers: typing.Dict[str, typing.Any]) -> None:
        pass

    @abc.abstractmethod
    def serialize(
        self, providers: typing.Dict[str, typing.Any]
    ) -> typing.Dict[str, typing.Any]:
        pass

    @staticmethod
    def client(grafana: str, providers: typing.Dict[str, typing.Any]) -> typing.Any:
        try:
            provider = providers[grafana]
        except KeyError:
            raise gdbt.errors.ProviderNotFound(grafana)
        return provider


@deserialize.downcast_identifier(Resource, "folder")
class Folder(Resource):
    @classmethod
    def create(
        cls,
        grafana: str,
        uid: str,
        model: typing.Dict[str, typing.Any],
        providers: typing.Dict[str, typing.Any],
    ) -> "Folder":
        try:
            title = model["title"]
            cls.client(grafana, providers).client.folder.create_folder(title, uid)
        except KeyError:
            raise gdbt.errors.DataError("Folder model missing 'title' key")
        except grafana_api.grafana_api.GrafanaException as exc:
            if exc.status_code != 412:
                raise gdbt.errors.GrafanaError(exc.message)
        folder = cls.get(grafana, uid, providers)
        return folder

    @classmethod
    def get(
        cls,
        grafana: str,
        uid: str,
        providers: typing.Dict[str, typing.Any],
    ) -> "Folder":
        try:
            title = cls.client(grafana, providers).client.folder.get_folder(uid)[
                "title"
            ]
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        model = {"title": title}
        folder = cls(grafana, uid, model)
        return folder

    @classmethod
    def exists(
        cls,
        grafana: str,
        uid: str,
        providers: typing.Dict[str, typing.Any],
    ) -> bool:
        try:
            cls.client(grafana, providers).client.folder.get_folder(uid)
        except grafana_api.grafana_api.GrafanaException as exc:
            if (
                isinstance(exc, grafana_api.grafana_api.GrafanaClientError)
                and exc.status_code == 404
            ):
                return False
            raise gdbt.errors.GrafanaError(exc.message)
        return True

    @classmethod
    def get_by_id(
        cls,
        grafana: str,
        id: int,
        providers: typing.Dict[str, typing.Any],
    ) -> "Folder":
        try:
            data = cls.client(grafana, providers).client.folder.get_folder_by_id(id)
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        model = {"title": data["title"]}
        uid = data["uid"]
        folder = cls(grafana, uid, model)
        return folder

    def id(self, providers: typing.Dict[str, typing.Any]) -> int:
        try:
            id = self.client(self.grafana, providers).client.folder.get_folder(
                self.uid
            )["id"]
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        return id

    def update(
        self,
        model: typing.Dict[str, typing.Any],
        providers: typing.Dict[str, typing.Any],
    ) -> None:
        try:
            title = model["title"]
            model = self.client(self.grafana, providers).client.folder.update_folder(
                self.uid, title, overwrite=True
            )
        except KeyError:
            raise gdbt.errors.DataError("Folder model missing 'title' key")
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)

    def delete(self, providers: typing.Dict[str, typing.Any]) -> None:
        try:
            self.client(self.grafana, providers).client.folder.delete_folder(self.uid)
        except grafana_api.grafana_api.GrafanaException as exc:
            if (
                isinstance(exc, grafana_api.grafana_api.GrafanaClientError)
                and exc.status_code == 404
            ):
                return
            raise gdbt.errors.GrafanaError(exc.message)

    def serialize(
        self, providers: typing.Dict[str, typing.Any]
    ) -> typing.Dict[str, typing.Any]:
        representation = {
            "kind": "folder",
            "grafana": self.grafana,
            "uid": self.uid,
            "model": self.model,
        }
        return representation


@deserialize.downcast_identifier(Resource, "dashboard")
@attr.s
class Dashboard(Resource):
    folder: str = attr.ib()

    @classmethod
    def create(
        cls,
        grafana: str,
        uid: str,
        model: typing.Dict[str, typing.Any],
        folder: str,
        providers: typing.Dict[str, typing.Any],
    ) -> "Dashboard":
        model.update({"id": None, "uid": uid, "version": 1})
        meta = {
            "dashboard": model,
            "folderId": Folder.get(grafana, folder, providers).id(providers),
            "overwrite": True,
        }
        try:
            model = cls.client(grafana, providers).client.dashboard.update_dashboard(
                meta
            )
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        return cls.get(grafana, uid, providers)

    @classmethod
    def get(
        cls,
        grafana: str,
        uid: str,
        providers: typing.Dict[str, typing.Any],
    ) -> "Dashboard":
        try:
            dashboard = cls.client(grafana, providers).client.dashboard.get_dashboard(
                uid
            )
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        model = dashboard["dashboard"]
        folder = Folder.get_by_id(grafana, dashboard["meta"]["folderId"], providers).uid
        for key in IGNORED_KEYS:
            model.pop(key, None)
        dashboard = cls(grafana, uid, model, folder)
        return dashboard

    @classmethod
    def exists(
        cls,
        grafana: str,
        uid: str,
        providers: typing.Dict[str, typing.Any],
    ) -> bool:
        try:
            cls.client(grafana, providers).client.dashboard.get_dashboard(uid)
        except grafana_api.grafana_api.GrafanaException as exc:
            if (
                isinstance(exc, grafana_api.grafana_api.GrafanaClientError)
                and exc.status_code == 404
            ):
                return False
            raise gdbt.errors.GrafanaError(exc.message)
        return True

    def id(self, providers: typing.Dict[str, typing.Any]) -> int:
        try:
            dashboard = self.client(
                self.grafana, providers
            ).client.dashboard.get_dashboard(self.uid)
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        id = dashboard["dashboard"]["id"]
        return id

    def version(self, providers: typing.Dict[str, typing.Any]) -> int:
        try:
            dashboard = self.client(
                self.grafana, providers
            ).client.dashboard.get_dashboard(self.uid)
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)
        version = dashboard["dashboard"]["version"]
        return version

    def update(
        self,
        model: typing.Dict[str, typing.Any],
        providers: typing.Dict[str, typing.Any],
    ) -> None:
        try:
            version_new = self.version(providers) + 1
        except TypeError:
            version_new = 1
        model.update(
            {"id": self.id(providers), "uid": self.uid, "version": version_new}
        )
        meta = {
            "dashboard": model,
            "folderId": Folder.get(self.grafana, self.folder, providers).id(providers),
            "overwrite": True,
        }
        try:
            model = self.client(
                self.grafana, providers
            ).client.dashboard.update_dashboard(meta)
        except grafana_api.grafana_api.GrafanaException as exc:
            raise gdbt.errors.GrafanaError(exc.message)

    def delete(self, providers: typing.Dict[str, typing.Any]) -> None:
        try:
            self.client(self.grafana, providers).client.dashboard.delete_dashboard(
                self.uid
            )
        except grafana_api.grafana_api.GrafanaException as exc:
            if (
                isinstance(exc, grafana_api.grafana_api.GrafanaClientError)
                and exc.status_code == 404
            ):
                return
            raise gdbt.errors.GrafanaError(exc.message)

    def serialize(
        self, providers: typing.Dict[str, typing.Any]
    ) -> typing.Dict[str, typing.Any]:
        representation = {
            "kind": "dashboard",
            "grafana": self.grafana,
            "uid": self.uid,
            "model": self.model,
            "folder": self.folder,
        }
        return representation
