module App.Utils exposing (..)

import App.Types
import Html exposing (..)
import Html.Attributes exposing (..)
import Http
import Json.Decode as JsonDecode
import Utils
import VirtualDom
import RemoteData exposing (WebData, RemoteData(..))


dropdown :
    (String -> a)
    -> List { b | name : String }
    -> Maybe String
    -> Html a
dropdown event items selected =
    div [ class "btn-group btn-dropdown" ]
        [ span
            [ type_ "button"
            , class "btn btn-secondary dropdown-toggle"
            , attribute "data-toggle" "dropdown"
            , attribute "aria-haspopup" "true"
            , attribute "aria-expanded" "false"
            ]
            [ text <| Maybe.withDefault "Select a value..." selected
            ]
        , span
            [ type_ "button"
            , class "btn btn-secondary dropdown-toggle"
            , attribute "data-toggle" "dropdown"
            , attribute "aria-haspopup" "true"
            , attribute "aria-expanded" "false"
            ]
            [ span [ class "sr-only" ] [ text "Toggle Dropdown" ]
            ]
        , div [ class "dropdown-menu" ]
            (List.map
                (\x ->
                    a
                        [ Utils.onClick (event x.name)
                        , class "dropdown-item"
                        ]
                        [ text x.name ]
                )
                items
            )
        ]


loading : VirtualDom.Node a
loading =
    div [ class "progress-wrapper" ]
        [ progress
            [ class "progress progress-striped progress-animated"
            , attribute "value" "100"
            , attribute "max" "100"
            ]
            [ text "Loading ..." ]
        , span [] [ text "Loading ..." ]
        ]


error : a -> String -> Html a
error event message =
    div
        [ class "alert alert-danger"
        , attribute "role" "alert"
        ]
        [ strong [] [ text "Error: " ]
        , span [] [ text message ]
        , a
            [ Utils.onClick event
            , class "alert-link"
            ]
            [ text " Click to retry." ]
        ]


getAlerts : WebData String -> List App.Types.Alert
getAlerts response =
    let
        decoderError =
            JsonDecode.map4 App.Types.ResponseError
                (JsonDecode.field "type" JsonDecode.string)
                (JsonDecode.field "detail" JsonDecode.string)
                (JsonDecode.field "status" JsonDecode.int)
                (JsonDecode.field "title" JsonDecode.string)

        handleError error =
            [ App.Types.Alert
                App.Types.AlertDanger
                "Error!"
                (case error of
                    Http.BadUrl url ->
                        ("Bad Url: " ++ url)

                    Http.Timeout ->
                        "Request Timeout"

                    Http.NetworkError ->
                        "A network error occured"

                    Http.BadPayload details response ->
                        ("Bad payload: " ++ details)

                    Http.BadStatus response ->
                        case JsonDecode.decodeString decoderError response.body of
                            Ok obj ->
                                obj.detail

                            Err error ->
                                error
                )
            ]
    in
        case response of
            Success r ->
                []

            Loading ->
                []

            NotAsked ->
                []

            Failure e ->
                handleError e


viewAlerts :
    List App.Types.Alert
    -> Html a
viewAlerts alerts =
    let
        getAlertTypeAsString alert =
            case alert.type_ of
                App.Types.AlertSuccess ->
                    "success"

                App.Types.AlertInfo ->
                    "info"

                App.Types.AlertWarning ->
                    "warning"

                App.Types.AlertDanger ->
                    "danger"

        createAlert alert =
            div [ class ("alert alert-" ++ (getAlertTypeAsString alert)) ]
                [ strong [] [ text alert.title ]
                , text alert.text
                ]
    in
        alerts
            |> List.map createAlert
            |> div []


appendItem : a -> List a -> List a
appendItem item items =
    List.append items [ item ]


appendItems : List a -> List a -> List a
appendItems items1 items2 =
    List.append items2 items1
