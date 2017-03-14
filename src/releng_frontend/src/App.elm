module App exposing (..)

import App.TreeStatus
import App.TreeStatus.Form
import App.TreeStatus.Types
import App.TryChooser
import App.Types
import App.UserScopes
import Hawk
import Navigation
import TaskclusterLogin
import Time
import UrlParser
import UrlParser exposing ((</>))


type Route
    = NotFoundRoute
    | HomeRoute
    | LoginRoute
    | LogoutRoute
    | TryChooserRoute
    | TreeStatusRoute App.TreeStatus.Types.Route


pages : List (App.Types.Page Route b)
pages =
    [ App.TryChooser.page TryChooserRoute
    , App.TreeStatus.page TreeStatusRoute
    ]


routes : UrlParser.Parser (Route -> a) a
routes =
    pages
        |> List.map (\x -> x.matcher)
        |> List.append
            [ UrlParser.map HomeRoute (UrlParser.s "")
            , UrlParser.map NotFoundRoute (UrlParser.s "404")
            , UrlParser.map LoginRoute (UrlParser.s "login")
            , UrlParser.map LogoutRoute (UrlParser.s "logout")
            ]
        |> UrlParser.oneOf


reverse : Route -> String
reverse route =
    case route of
        NotFoundRoute ->
            "/404"

        HomeRoute ->
            "/"

        LoginRoute ->
            "/login"

        LogoutRoute ->
            "/logout"

        TryChooserRoute ->
            "/trychooser"

        TreeStatusRoute route ->
            App.TreeStatus.reverse route


urlParser : Navigation.Location -> Msg
urlParser location =
    -- TODO: parse location into a route
    NavigateTo HomeRoute



--    let
--        parse address =
--            address
--                |> UrlParser.parse identity routes
--                |> Result.withDefault NotFoundRoute
--
--        resolver =
--            Hop.makeResolver App.Types.hopConfig parse
--    in
--        Navigation.makeParser (.href >> resolver)


type alias Model =
    { location : Navigation.Location
    , route : Route
    , user : TaskclusterLogin.Model
    , userScopes : App.UserScopes.Model
    , trychooser : App.TryChooser.Model
    , treestatus : App.TreeStatus.Types.Model App.TreeStatus.Form.AddTree App.TreeStatus.Form.UpdateTree
    , docsUrl : String
    , version : String
    }


type Msg
    = Tick Time.Time
    | TaskclusterLoginMsg TaskclusterLogin.Msg
    | HawkMsg Hawk.Msg
    | NavigateTo Route
    | UserScopesMsg App.UserScopes.Msg
    | TryChooserMsg App.TryChooser.Msg
    | TreeStatusMsg App.TreeStatus.Types.Msg


type alias Flags =
    { user : TaskclusterLogin.Model
    , treestatusUrl : String
    , docsUrl : String
    , version : String
    }
