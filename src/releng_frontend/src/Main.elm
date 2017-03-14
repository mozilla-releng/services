module Main exposing (..)

import App
import App.Home
import App.Layout
import App.TreeStatus
import App.TreeStatus.Api
import App.TreeStatus.Types
import App.TryChooser
import App.UserScopes
import Hawk
import Html exposing (..)
import Navigation
import String
import Dict
import TaskclusterLogin
import Time
import Utils


init : App.Flags -> Navigation.Location -> ( App.Model, Cmd App.Msg )
init flags location =
    ( { location = location
      , route = App.HomeRoute
      , docsUrl = flags.docsUrl
      , version = flags.version
      , user = flags.user
      , userScopes = App.UserScopes.init
      , trychooser = App.TryChooser.init
      , treestatus = App.TreeStatus.init flags.treestatusUrl
      }
    , Utils.performMsg (App.NavigateTo App.HomeRoute)
    )


update : App.Msg -> App.Model -> ( App.Model, Cmd App.Msg )
update msg model =
    case msg of
        App.Tick newTime ->
            case model.user of
                Just user ->
                    case user.certificate of
                        Just certificate ->
                            let
                                expired =
                                    newTime > (toFloat certificate.expiry)

                                logout =
                                    App.TaskclusterLoginMsg TaskclusterLogin.Logout
                            in
                                if expired then
                                    update logout model
                                else
                                    ( model, Cmd.none )

                        Nothing ->
                            ( model, Cmd.none )

                Nothing ->
                    ( model, Cmd.none )

        App.TaskclusterLoginMsg userMsg ->
            let
                ( newUser, userCmd ) =
                    TaskclusterLogin.update userMsg model.user
            in
                ( { model | user = newUser }
                , Cmd.map App.TaskclusterLoginMsg userCmd
                )

        App.HawkMsg hawkMsg ->
            let
                ( requestId, cmd, response ) =
                    Hawk.update hawkMsg

                routeHawkMsg route =
                    if String.startsWith "TreeStatus" route then
                        route
                            |> String.dropLeft (String.length "TreeStatus")
                            |> App.TreeStatus.Api.hawkResponse response
                            |> Cmd.map App.TreeStatusMsg
                    else if String.startsWith "UserScopes" route then
                        route
                            |> String.dropLeft (String.length "UserScopes")
                            |> App.UserScopes.hawkResponse response
                            |> Cmd.map App.UserScopesMsg
                    else
                        Cmd.none

                appCmd =
                    requestId
                        |> Maybe.map routeHawkMsg
                        |> Maybe.withDefault Cmd.none
            in
                ( model
                , Cmd.batch
                    [ Cmd.map App.HawkMsg cmd
                    , appCmd
                    ]
                )

        App.NavigateTo route ->
            let
                newCmd =
                    (App.reverse route)
                        |> Navigation.newUrl

                goHome =
                    App.NavigateTo App.HomeRoute

                -- TODO: parse url query into dict
                urlQuery =
                    Dict.empty

                login =
                    urlQuery
                        |> TaskclusterLogin.convertUrlQueryToUser
                        |> Maybe.map
                            (\x ->
                                x
                                    |> TaskclusterLogin.Logging
                                    |> App.TaskclusterLoginMsg
                            )
                        |> Maybe.withDefault goHome

                logout =
                    App.TaskclusterLoginMsg TaskclusterLogin.Logout

                fetchUserScopes =
                    App.UserScopesMsg App.UserScopes.FetchScopes
            in
                case route of
                    App.NotFoundRoute ->
                        ( model, newCmd )

                    App.HomeRoute ->
                        { model
                            | trychooser = App.TryChooser.init
                            , treestatus =
                                App.TreeStatus.init model.treestatus.baseUrl
                        }
                            ! [ newCmd ]
                            |> Utils.andThen update fetchUserScopes

                    App.LoginRoute ->
                        model
                            ! []
                            |> Utils.andThen update login
                            |> Utils.andThen update goHome

                    App.LogoutRoute ->
                        model
                            ! []
                            |> Utils.andThen update logout
                            |> Utils.andThen update goHome

                    App.TryChooserRoute ->
                        update (App.TryChooserMsg App.TryChooser.Load) model
                            |> Utils.andThen update fetchUserScopes

                    App.TreeStatusRoute route ->
                        update (App.TreeStatusMsg (App.TreeStatus.Types.NavigateTo route)) model
                            |> Utils.andThen update fetchUserScopes

        App.UserScopesMsg msg2 ->
            let
                ( newModel, newCmd, hawkCmd ) =
                    App.UserScopes.update msg2 model.userScopes
            in
                ( { model | userScopes = newModel }
                , hawkCmd
                    |> Maybe.map (\req -> [ hawkSend model.user "UserScopes" req ])
                    |> Maybe.withDefault []
                    |> List.append [ Cmd.map App.UserScopesMsg newCmd ]
                    |> Cmd.batch
                )

        App.TryChooserMsg msg2 ->
            let
                ( newModel, newCmd ) =
                    App.TryChooser.update msg2 model.trychooser
            in
                ( { model | trychooser = newModel }
                , Cmd.map App.TryChooserMsg newCmd
                )

        App.TreeStatusMsg msg2 ->
            let
                route =
                    case model.route of
                        App.TreeStatusRoute x ->
                            x

                        _ ->
                            App.TreeStatus.Types.ShowTreesRoute

                ( newModel, newCmd, hawkCmd ) =
                    App.TreeStatus.update route msg2 model.treestatus
            in
                ( { model | treestatus = newModel }
                , hawkCmd
                    |> Maybe.map (\req -> [ hawkSend model.user "TreeStatus" req ])
                    |> Maybe.withDefault []
                    |> List.append [ Cmd.map App.TreeStatusMsg newCmd ]
                    |> Cmd.batch
                )


hawkSend :
    TaskclusterLogin.Model
    -> String
    -> Hawk.Request
    -> Cmd App.Msg
hawkSend user page request =
    let
        pagedRequest =
            { request | id = (page ++ request.id) }
    in
        case user of
            Just user2 ->
                Hawk.send request user2
                    |> Cmd.map App.HawkMsg

            Nothing ->
                Cmd.none


viewRoute : App.Model -> Html App.Msg
viewRoute model =
    case model.route of
        App.NotFoundRoute ->
            App.Layout.viewNotFound model

        App.HomeRoute ->
            App.Home.view model

        App.LoginRoute ->
            -- TODO: this should be already a view on TaskclusterLogin
            text "Logging you in ..."

        App.LogoutRoute ->
            -- TODO: this should be already a view on TaskclusterLogin
            text "Logging you out ..."

        App.TryChooserRoute ->
            Html.map App.TryChooserMsg (App.TryChooser.view model.trychooser)

        App.TreeStatusRoute route ->
            App.TreeStatus.view
                route
                model.userScopes.scopes
                model.treestatus
                |> Html.map App.TreeStatusMsg


subscriptions : App.Model -> Sub App.Msg
subscriptions model =
    Sub.batch
        [ TaskclusterLogin.subscriptions App.TaskclusterLoginMsg
        , Hawk.subscriptions App.HawkMsg
        , Time.every Time.second App.Tick
        ]


main : Program App.Flags App.Model App.Msg
main =
    Navigation.programWithFlags App.urlParser
        { init = init
        , view = App.Layout.view viewRoute
        , update = update
        , subscriptions = subscriptions
        }
