module App.TreeStatus.Api exposing (..)

import App.TreeStatus.Types
import Http
import Json.Decode as JsonDecode
import Json.Encode as JsonEncode
import RemoteData exposing (WebData)


encoderUpdateTree :
    { a
        | message_of_the_day : String
        , reason : String
        , remember : Bool
        , status : String
        , trees : List String
        , tags : List String
    }
    -> JsonEncode.Value
encoderUpdateTree data =
    JsonEncode.object
        [ ( "trees", JsonEncode.list (List.map JsonEncode.string data.trees) )
        , ( "status", JsonEncode.string data.status )
        , ( "reason", JsonEncode.string data.reason )
        , ( "tags", JsonEncode.list (List.map JsonEncode.string data.tags) )
        , ( "message_of_the_day", JsonEncode.string data.message_of_the_day )
        , ( "remember", JsonEncode.bool data.remember )
        ]


encoderUpdateTrees :
    { a
        | reason : String
        , remember : Bool
        , status : String
        , trees : List String
        , tags : List String
    }
    -> JsonEncode.Value
encoderUpdateTrees data =
    JsonEncode.object
        [ ( "trees", JsonEncode.list (List.map JsonEncode.string data.trees) )
        , ( "status", JsonEncode.string data.status )
        , ( "reason", JsonEncode.string data.reason )
        , ( "tags", JsonEncode.list (List.map JsonEncode.string data.tags) )
        , ( "remember", JsonEncode.bool data.remember )
        ]


encoderTree : App.TreeStatus.Types.Tree -> JsonEncode.Value
encoderTree tree =
    JsonEncode.object
        [ ( "tree", JsonEncode.string tree.name )
        , ( "status", JsonEncode.string tree.status )
        , ( "reason", JsonEncode.string tree.reason )
        , ( "message_of_the_day", JsonEncode.string tree.message_of_the_day )
        ]


encoderTreeNames : App.TreeStatus.Types.Trees -> JsonEncode.Value
encoderTreeNames trees =
    JsonEncode.list (List.map (\x -> JsonEncode.string x.name) trees)


decoderTrees : JsonDecode.Decoder App.TreeStatus.Types.Trees
decoderTrees =
    JsonDecode.list decoderTree2
        |> JsonDecode.at [ "result" ]


decoderTree2 : JsonDecode.Decoder App.TreeStatus.Types.Tree
decoderTree2 =
    JsonDecode.map4 App.TreeStatus.Types.Tree
        (JsonDecode.field "tree" JsonDecode.string)
        (JsonDecode.field "status" JsonDecode.string)
        (JsonDecode.field "reason" JsonDecode.string)
        (JsonDecode.field "message_of_the_day" JsonDecode.string)


decoderTree : JsonDecode.Decoder App.TreeStatus.Types.Tree
decoderTree =
    JsonDecode.at [ "result" ] decoderTree2


decoderTreeLogs : JsonDecode.Decoder App.TreeStatus.Types.TreeLogs
decoderTreeLogs =
    JsonDecode.list decoderTreeLog
        |> JsonDecode.at [ "result" ]


decoderTreeLog : JsonDecode.Decoder App.TreeStatus.Types.TreeLog
decoderTreeLog =
    JsonDecode.map6 App.TreeStatus.Types.TreeLog
        (JsonDecode.field "tree" JsonDecode.string)
        (JsonDecode.field "when" JsonDecode.string)
        (JsonDecode.field "who" JsonDecode.string)
        (JsonDecode.field "status" JsonDecode.string)
        (JsonDecode.field "reason" JsonDecode.string)
        (JsonDecode.field "tags" (JsonDecode.list JsonDecode.string))


decoderRecentChanges : JsonDecode.Decoder (List App.TreeStatus.Types.RecentChange)
decoderRecentChanges =
    JsonDecode.list decoderRecentChange
        |> JsonDecode.at [ "result" ]


decoderRecentChange : JsonDecode.Decoder App.TreeStatus.Types.RecentChange
decoderRecentChange =
    JsonDecode.map6 App.TreeStatus.Types.RecentChange
        (JsonDecode.field "id" JsonDecode.int)
        (JsonDecode.field "trees" (JsonDecode.list JsonDecode.string))
        (JsonDecode.field "when" JsonDecode.string)
        (JsonDecode.field "who" JsonDecode.string)
        (JsonDecode.field "status" JsonDecode.string)
        (JsonDecode.field "reason" JsonDecode.string)


get :
    (RemoteData.RemoteData Http.Error a -> b)
    -> String
    -> JsonDecode.Decoder a
    -> Cmd b
get msg url decoder =
    Http.get url decoder
        |> Http.toTask
        |> RemoteData.asCmd
        |> Cmd.map msg


fetchTrees :
    String
    -> Cmd App.TreeStatus.Types.Msg
fetchTrees url =
    get App.TreeStatus.Types.GetTreesResult
        (url ++ "/trees2")
        decoderTrees


fetchTree :
    String
    -> String
    -> Cmd App.TreeStatus.Types.Msg
fetchTree url name =
    get App.TreeStatus.Types.GetTreeResult
        (url ++ "/trees/" ++ name)
        decoderTree


fetchTreeLogs :
    String
    -> String
    -> Bool
    -> Cmd App.TreeStatus.Types.Msg
fetchTreeLogs url name all =
    case all of
        True ->
            get App.TreeStatus.Types.GetTreeLogsAllResult
                (url ++ "/trees/" ++ name ++ "/logs?all=1")
                decoderTreeLogs

        False ->
            get App.TreeStatus.Types.GetTreeLogsResult
                (url ++ "/trees/" ++ name ++ "/logs?all=0")
                decoderTreeLogs


fetchRecentChanges :
    String
    -> Cmd App.TreeStatus.Types.Msg
fetchRecentChanges url =
    get App.TreeStatus.Types.GetRecentChangesResult
        (url ++ "/stack")
        decoderRecentChanges


hawkResponse :
    Cmd (WebData String)
    -> String
    -> Cmd App.TreeStatus.Types.Msg
hawkResponse response route =
    case route of
        "AddTree" ->
            Cmd.map App.TreeStatus.Types.FormAddTreeResult response

        "DeleteTrees" ->
            Cmd.map App.TreeStatus.Types.DeleteTreesResult response

        "UpdateTrees" ->
            Cmd.map App.TreeStatus.Types.FormUpdateTreesResult response

        "RevertChange" ->
            Cmd.map App.TreeStatus.Types.RecentChangeResult response

        "DiscardChange" ->
            Cmd.map App.TreeStatus.Types.RecentChangeResult response

        _ ->
            Cmd.none
